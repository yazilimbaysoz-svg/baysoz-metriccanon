"""Baysöz Labs <baysozlabs@proton.me> — auditable, content-addressed baselines."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import Finding, Report
from .rules import RULE_BY_ID

BASELINE_SCHEMA = "baysoz-metriccanon/baseline-v1"
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{32}$")


class BaselineError(ValueError):
    pass


@dataclass(frozen=True)
class AcceptedFinding:
    fingerprint: str
    rule_id: str
    reason: str


def load_baseline(path: str | None) -> dict[str, AcceptedFinding]:
    if path is None:
        return {}
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineError(f"cannot read baseline {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != BASELINE_SCHEMA:
        raise BaselineError(f"baseline schema must be {BASELINE_SCHEMA}")
    entries = raw.get("accepted")
    if not isinstance(entries, list):
        raise BaselineError("baseline accepted must be a list")
    result: dict[str, AcceptedFinding] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"fingerprint", "rule_id", "reason"}:
            raise BaselineError(f"baseline accepted[{index}] has invalid keys")
        fingerprint = entry["fingerprint"]
        rule_id = entry["rule_id"]
        reason = entry["reason"]
        if not isinstance(fingerprint, str) or not _FINGERPRINT_RE.fullmatch(fingerprint):
            raise BaselineError(f"baseline accepted[{index}].fingerprint must be 32 hex characters")
        if not isinstance(rule_id, str) or rule_id not in RULE_BY_ID:
            raise BaselineError(f"baseline accepted[{index}].rule_id is unknown")
        if not isinstance(reason, str) or not reason.strip():
            raise BaselineError(f"baseline accepted[{index}].reason must be non-empty")
        if fingerprint in result:
            raise BaselineError(f"baseline fingerprint {fingerprint} is duplicated")
        result[fingerprint] = AcceptedFinding(fingerprint, rule_id, reason)
    return result


def apply_baseline(report: Report, accepted: dict[str, AcceptedFinding], source: str) -> Report:
    current = {finding.fingerprint for finding in report.findings}
    updated: list[Finding] = []
    for finding in report.findings:
        entry = accepted.get(finding.fingerprint)
        updated.append(finding.with_suppression(entry.reason) if entry is not None else finding)
    for fingerprint, entry in sorted(accepted.items()):
        if fingerprint in current:
            continue
        updated.append(
            Finding(
                rule_id="MC014",
                level="warning",
                message=(
                    f"baseline entry {fingerprint} for rule {entry.rule_id} no longer matches "
                    "the analyzed input"
                ),
                source=source,
                evidence=(
                    ("fingerprint", fingerprint),
                    ("rule_id", entry.rule_id),
                    ("reason", entry.reason),
                ),
            )
        )
    updated.sort(key=lambda f: (f.rule_id, f.source, f.message, f.fingerprint))
    return Report(
        input_digest=report.input_digest,
        point_count=report.point_count,
        resource_count=report.resource_count,
        findings=tuple(updated),
    )


def write_baseline(
    report: Report, path: str, reason: str, input_path: str, policy_digest: str
) -> None:
    entries: list[dict[str, str]] = []
    for finding in report.findings:
        if finding.suppressed:
            continue
        entries.append(
            {
                "fingerprint": finding.fingerprint,
                "rule_id": finding.rule_id,
                "reason": reason,
            }
        )
    document: dict[str, Any] = {
        "schema": BASELINE_SCHEMA,
        "attribution": "Baysöz Labs <baysozlabs@proton.me>",
        "source_input": input_path,
        "input_digest": report.input_digest,
        "policy_digest": policy_digest,
        "accepted": sorted(entries, key=lambda item: item["fingerprint"]),
    }
    Path(path).write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
