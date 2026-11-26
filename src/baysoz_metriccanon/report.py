"""Baysöz Labs <baysozlabs@proton.me> — deterministic SARIF 2.1.0 and text renderers."""

from __future__ import annotations

from typing import Any

from .model import Finding, Report, evidence_text
from .policy import Policy
from .rules import RULES
from .version import __attribution__ as ATTRIBUTION
from .version import __version__

SCHEMA = "baysoz-metriccanon/report-v1"
REPOSITORY = "https://github.com/yazilimbaysoz-svg/baysoz-metriccanon"


def _finding_json(finding: Finding) -> dict[str, Any]:
    return {
        "rule_id": finding.rule_id,
        "level": finding.level,
        "message": finding.message,
        "source": finding.source,
        "evidence": dict(finding.evidence),
        "fingerprint": finding.fingerprint,
        "suppressed": finding.suppressed,
        "suppression_reason": finding.suppression_reason,
    }


def json_document(report: Report, policy: Policy, input_path: str, fail_on: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "attribution": ATTRIBUTION,
        "tool": f"baysoz-metriccanon {__version__}",
        "repository": REPOSITORY,
        "input": input_path,
        "input_digest": report.input_digest,
        "policy_source": policy.source,
        "policy_digest": policy.digest,
        "report_digest": report.digest,
        "counts": {
            "points": report.point_count,
            "resources": report.resource_count,
            "errors": report.errors,
            "warnings": report.warnings,
            "suppressed": report.suppressed_count,
        },
        "fail_on": fail_on,
        "gate": "FAIL" if report.gate_failed(fail_on) else "PASS",
        "findings": [_finding_json(finding) for finding in report.findings],
    }


def sarif_document(report: Report, policy: Policy, input_path: str, fail_on: str) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    for rule in RULES:
        rules.append(
            {
                "id": rule.rule_id,
                "name": rule.name,
                "shortDescription": {"text": rule.short_description},
                "fullDescription": {"text": rule.guidance},
                "defaultConfiguration": {"level": rule.default_level},
                "help": {"text": f"{rule.guidance} — {ATTRIBUTION}"},
            }
        )
    results: list[dict[str, Any]] = []
    for finding in report.findings:
        result: dict[str, Any] = {
            "ruleId": finding.rule_id,
            "level": "none" if finding.suppressed else finding.level,
            "message": {"text": finding.message},
            "logicalLocations": [{"name": finding.source, "fullyQualifiedName": finding.source}],
            "partialFingerprints": {"baysozMetriccanon/v1": finding.fingerprint},
            "properties": {
                "evidence": dict(finding.evidence),
                "inputDigest": report.input_digest,
                "attribution": ATTRIBUTION,
            },
        }
        if finding.suppressed:
            result["suppressions"] = [
                {"kind": "external", "justification": finding.suppression_reason}
            ]
        results.append(result)
    failed = report.gate_failed(fail_on)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "baysoz-metriccanon",
                        "version": __version__,
                        "fullName": f"{ATTRIBUTION} — baysoz-metriccanon",
                        "informationUri": REPOSITORY,
                        "rules": rules,
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": not failed,
                        "exitCode": 1 if failed else 0,
                        "commandLine": f"baysoz-metriccanon {input_path} --fail-on {fail_on}",
                    }
                ],
                "results": results,
                "properties": {
                    "attribution": ATTRIBUTION,
                    "input": input_path,
                    "inputDigest": report.input_digest,
                    "policyDigest": policy.digest,
                    "reportDigest": report.digest,
                    "gate": "FAIL" if failed else "PASS",
                    "points": report.point_count,
                    "resources": report.resource_count,
                },
            }
        ],
    }


def render_text(report: Report, input_path: str, fail_on: str, policy_source: str) -> str:
    gate = "FAIL" if report.gate_failed(fail_on) else "PASS"
    lines = [
        f"{ATTRIBUTION} — baysoz-metriccanon {__version__}",
        f"input: {input_path} (sha256 {report.input_digest[:16]})",
        f"policy: {policy_source}",
        (
            f"points: {report.point_count} | resources: {report.resource_count} | "
            f"findings: {len(report.findings)} "
            f"(errors: {report.errors}, warnings: {report.warnings}, "
            f"suppressed: {report.suppressed_count})"
        ),
    ]
    if not report.findings:
        lines.append("status: no semantic invariant violations detected")
    for finding in report.findings:
        marker = "suppressed" if finding.suppressed else finding.level
        lines.append(f"{finding.rule_id} [{marker}] {finding.message}")
        lines.append(f"  source: {finding.source}")
        if finding.evidence:
            lines.append(f"  evidence: {evidence_text(finding)}")
        if finding.suppressed:
            lines.append(f"  reason: {finding.suppression_reason}")
    lines.append(f"gate: {gate} (--fail-on {fail_on})")
    lines.append(f"signed off by {ATTRIBUTION}")
    return "\n".join(lines)
