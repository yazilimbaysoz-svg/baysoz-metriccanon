"""Baysöz Labs <baysozlabs@proton.me> — semantic invariant and deterministic report tests."""

from __future__ import annotations

import json
from pathlib import Path

from baysoz_metriccanon import (
    RULE_BY_ID,
    analyze,
    apply_baseline,
    default_policy,
    json_document,
    load_baseline,
    load_policy,
    parse_input,
    read_input,
    render_text,
    sarif_document,
    write_baseline,
)

FIXTURES = Path(__file__).parent / "fixtures"


def report_for(name: str, policy=None):
    raw, digest = read_input(str(FIXTURES / name))
    points, _services = parse_input(raw, name, policy or default_policy())
    return analyze(points, policy or default_policy(), digest)


def test_clean_snapshot_passes_all_invariants():
    report = report_for("clean.snapshot.json")
    assert report.findings == ()
    assert report.errors == 0
    assert report.gate_failed("error") is False
    assert "no semantic invariant violations" in render_text(
        report, "clean.snapshot.json", "error", "built-in"
    )


def test_adversarial_snapshot_exercises_every_implemented_rule():
    report = report_for("adversarial.snapshot.json")
    fired = {finding.rule_id for finding in report.findings}
    expected = set(RULE_BY_ID) - {"MC014"}
    assert expected <= fired
    assert len(report.findings) >= len(expected)


def test_findings_are_evidence_backed_and_content_addressed():
    report = report_for("adversarial.snapshot.json")
    for finding in report.findings:
        assert finding.rule_id in RULE_BY_ID
        assert finding.message and finding.source
        assert len(finding.fingerprint) == 32
        assert finding.level in {"error", "warning"}
    fingerprints = [finding.fingerprint for finding in report.findings]
    assert len(fingerprints) == len(set(fingerprints))


def test_reports_are_byte_deterministic():
    first = report_for("adversarial.snapshot.json")
    second = report_for("adversarial.snapshot.json")
    assert first.digest == second.digest
    policy = default_policy()
    one = json_document(first, policy, "adversarial.snapshot.json", "error")
    two = json_document(second, policy, "adversarial.snapshot.json", "error")
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)
    assert "Baysöz Labs <baysozlabs@proton.me>" in one["attribution"]


def test_sarif_document_is_well_formed():
    report = report_for("adversarial.snapshot.json")
    document = sarif_document(report, default_policy(), "adversarial.snapshot.json", "error")
    assert document["version"] == "2.1.0"
    run = document["runs"][0]
    assert run["tool"]["driver"]["name"] == "baysoz-metriccanon"
    assert "Baysöz Labs <baysozlabs@proton.me>" in run["tool"]["driver"]["fullName"]
    assert run["invocations"][0]["exitCode"] == 1
    assert len(run["results"]) == len(report.findings)
    for result in run["results"]:
        assert result["ruleId"] in RULE_BY_ID
        assert result["partialFingerprints"]["baysozMetriccanon/v1"]
        assert result["message"]["text"]
        assert result["logicalLocations"][0]["fullyQualifiedName"]


def test_baseline_suppresses_only_matching_findings(tmp_path: Path):
    report = report_for("adversarial.snapshot.json")
    path = tmp_path / "baseline.json"
    write_baseline(report, str(path), "reviewed", "adversarial.snapshot.json", "policy-digest")
    accepted = load_baseline(str(path))
    assert len(accepted) == len(report.findings)
    suppressed = apply_baseline(report, accepted, "baseline:baseline.json")
    assert suppressed.suppressed_count == len(report.findings)
    assert suppressed.gate_failed("error") is False
    partial = dict(list(accepted.items())[:1])
    mixed = apply_baseline(report, partial, "baseline:baseline.json")
    assert mixed.suppressed_count == 1
    stale = [
        finding
        for finding in apply_baseline(
            report_for("clean.snapshot.json"), accepted, "baseline:baseline.json"
        ).findings
        if finding.rule_id == "MC014"
    ]
    assert len(stale) == len(accepted)
    assert all(finding.level == "warning" for finding in stale)


def test_otlp_fixture_detects_counter_regression():
    report = report_for("adversarial.otlp.json")
    messages = [finding.message for finding in report.findings]
    assert any("decreased from 10 to 8" in message for message in messages)


def test_prometheus_histogram_drift_is_flagged():
    report = report_for("prometheus.drift.txt")
    fired = {finding.rule_id for finding in report.findings}
    assert {"MC005", "MC015"} <= fired


def test_policy_extends_unit_and_name_catalogs(tmp_path: Path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "schema": "baysoz-metriccanon/policy-v1",
                "unit_aliases": {"furlong": "1"},
                "canonical_names": {"legacy.duration": "modern.duration"},
            }
        ),
        encoding="utf-8",
    )
    policy = load_policy(str(policy_path))
    report = report_for("adversarial.snapshot.json", policy)
    fired = {finding.rule_id for finding in report.findings}
    assert "MC003" not in fired
    assert "MC008" in fired
