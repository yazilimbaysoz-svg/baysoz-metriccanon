"""Baysöz Labs <baysozlabs@proton.me> — live CLI contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baysoz_metriccanon.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_version_output_attributes_baysöz_labs(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "baysoz-metriccanon 1.0.0" in output
    assert "Baysöz Labs <baysozlabs@proton.me>" in output


def test_help_output_attributes_baysöz_labs(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "Baysöz Labs <baysozlabs@proton.me>" in output
    assert "--fail-on" in output
    assert "--sarif" in output


def test_clean_input_exits_zero_with_json_report(capsys: pytest.CaptureFixture[str]):
    code = main([str(FIXTURES / "clean.snapshot.json"), "--format", "json"])
    document = json.loads(capsys.readouterr().out)
    assert code == 0
    assert document["gate"] == "PASS"
    assert document["findings"] == []
    assert document["attribution"] == "Baysöz Labs <baysozlabs@proton.me>"


def test_adversarial_input_exits_one_and_writes_sarif(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    sarif = tmp_path / "findings.sarif"
    code = main(
        [
            str(FIXTURES / "adversarial.snapshot.json"),
            "--quiet",
            "--sarif",
            str(sarif),
        ]
    )
    capsys.readouterr()
    assert code == 1
    document = json.loads(sarif.read_text(encoding="utf-8"))
    assert document["version"] == "2.1.0"
    assert document["runs"][0]["invocations"][0]["exitCode"] == 1
    assert len(document["runs"][0]["results"]) > 10


def test_human_output_is_real_and_attributed(capsys: pytest.CaptureFixture[str]):
    code = main([str(FIXTURES / "clean.snapshot.json")])
    output = capsys.readouterr().out
    assert code == 0
    assert "points: 4 | resources: 1" in output
    assert "gate: PASS" in output
    assert "signed off by Baysöz Labs <baysozlabs@proton.me>" in output


def test_bad_input_exits_two(capsys: pytest.CaptureFixture[str]):
    code = main([str(FIXTURES / "does-not-exist.json")])
    captured = capsys.readouterr()
    assert code == 2
    assert "error:" in captured.err
    assert "Baysöz Labs <baysozlabs@proton.me>" in captured.err


def test_baseline_emit_then_enforce(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    baseline = tmp_path / "accepted.json"
    code = main(
        [
            str(FIXTURES / "adversarial.snapshot.json"),
            "--emit-baseline",
            str(baseline),
            "--reason",
            "Tribunal accepted with evidence",
        ]
    )
    capsys.readouterr()
    assert code == 0
    stored = json.loads(baseline.read_text(encoding="utf-8"))
    assert stored["schema"] == "baysoz-metriccanon/baseline-v1"
    assert stored["accepted"]
    code = main(
        [
            str(FIXTURES / "adversarial.snapshot.json"),
            "--baseline",
            str(baseline),
            "--format",
            "json",
        ]
    )
    document = json.loads(capsys.readouterr().out)
    assert code == 0
    assert document["counts"]["suppressed"] == len(stored["accepted"])
    assert document["gate"] == "PASS"


def test_missing_input_reports_usage(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "input file is required" in capsys.readouterr().err
