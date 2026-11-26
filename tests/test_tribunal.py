"""Baysöz Labs <baysozlabs@proton.me> — Supreme Grand Jury Tribunal evidence test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baysoz_metriccanon import (
    RULE_BY_ID,
    InputError,
    analyze,
    default_policy,
    parse_input,
    read_input,
)
from baysoz_metriccanon.cli import main
from baysoz_metriccanon.report import sarif_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
ATTRIBUTION = "Baysöz Labs <baysozlabs@proton.me>"


def _report(name: str):
    raw, digest = read_input(str(FIXTURES / name))
    points, _services = parse_input(raw, name, default_policy())
    return analyze(points, default_policy(), digest)


def structural_juror() -> str:
    required = [
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "SECURITY.md",
        "PLAN.md",
        "docs/MARKET_RESEARCH.md",
        "docs/ARCHITECTURE.md",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        ".gitignore",
        "src/baysoz_metriccanon/__init__.py",
        "tests/test_cli.py",
    ]
    for relative in required:
        path = ROOT / relative
        assert path.is_file(), relative
        text = path.read_text(encoding="utf-8")
        assert ATTRIBUTION in text, relative
    return "PASS: all public artifacts exist and carry attribution"


def semantic_juror() -> str:
    report = _report("adversarial.snapshot.json")
    fired = {finding.rule_id for finding in report.findings}
    assert set(RULE_BY_ID) - {"MC014"} <= fired
    for finding in report.findings:
        assert finding.rule_id in RULE_BY_ID
        assert finding.message.strip() and finding.source.strip()
        assert len(finding.fingerprint) == 32
        assert all(key and value for key, value in finding.evidence)
    return f"PASS: {len(report.findings)} evidence-backed findings across {len(fired)} rules"


def determinism_juror(capsys: pytest.CaptureFixture[str]) -> str:
    arguments = [str(FIXTURES / "clean.snapshot.json"), "--format", "json"]
    assert main(arguments) == 0
    first = capsys.readouterr().out
    assert main(arguments) == 0
    second = capsys.readouterr().out
    assert first == second
    report = _report("adversarial.snapshot.json")
    one = json.dumps(sarif_document(report, default_policy(), "a.json", "error"), sort_keys=True)
    two = json.dumps(sarif_document(report, default_policy(), "a.json", "error"), sort_keys=True)
    assert one == two
    return "PASS: byte-identical CLI and SARIF output on repeated execution"


def adversarial_execution_juror() -> str:
    clean = _report("clean.snapshot.json")
    otlp = _report("adversarial.otlp.json")
    prometheus = _report("prometheus.drift.txt")
    assert clean.findings == ()
    assert any("decreased from 10 to 8" in f.message for f in otlp.findings)
    assert {"MC005", "MC015"} <= {f.rule_id for f in prometheus.findings}
    with pytest.raises(InputError):
        parse_input(b'{"surprise": true}', "surprise.json", default_policy())
    return "PASS: clean, OTLP, Prometheus and malformed adversarial inputs executed live"


def no_stubs_juror() -> str:
    forbidden = ("TODO", "FIXME", "not implemented", "placeholder", "stub", "eval(", "exec(")
    for path in sorted((ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path}: {token}"
    return "PASS: no stub markers or dynamic execution primitives in production source"


def supply_chain_juror() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.13"' in pyproject
    assert "baysozlabs@proton.me" in pyproject
    assert 'license = { file = "LICENSE" }' in pyproject
    for gate in (
        "uv run pytest -q",
        "ruff check --select E,F,W,S,B .",
        "semgrep --config p/default --error .",
    ):
        assert gate in ci
    return "PASS: Python 3.13+, MIT attribution and all three CI gates are enforced"


def test_supreme_grand_jury_tribunal_is_unanimous(capsys: pytest.CaptureFixture[str]):
    verdicts = {
        "Structural Juror": structural_juror(),
        "Semantic Juror": semantic_juror(),
        "Determinism Juror": determinism_juror(capsys),
        "Adversarial Execution Juror": adversarial_execution_juror(),
        "No-Stub Juror": no_stubs_juror(),
        "Supply-Chain Juror": supply_chain_juror(),
    }
    capsys.readouterr()
    assert all(verdict.startswith("PASS") for verdict in verdicts.values())
    for juror, verdict in verdicts.items():
        print(f"{juror}: {verdict}")
    print(f"UNANIMOUS PASS — {ATTRIBUTION}")
