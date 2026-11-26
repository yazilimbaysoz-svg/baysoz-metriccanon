"""Baysöz Labs <baysozlabs@proton.me> — baysoz-metriccanon domain model."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

AttributeValue = str | int | float | bool


@dataclass(frozen=True)
class Attribute:
    key: str
    value: AttributeValue
    source: str

    @property
    def type_name(self) -> str:
        if isinstance(self.value, bool):
            return "bool"
        if isinstance(self.value, int):
            return "int"
        if isinstance(self.value, float):
            return "float"
        return "str"


@dataclass(frozen=True)
class Resource:
    service_name: str | None
    attributes: tuple[Attribute, ...]
    source: str

    @property
    def identity(self) -> str:
        if self.service_name:
            return self.service_name
        return "unknown-service"


@dataclass(frozen=True)
class Exemplar:
    trace_id: str
    span_id: str
    source: str


@dataclass(frozen=True)
class Histogram:
    count: float | None
    total: float | None
    bounds: tuple[float, ...]
    bucket_counts: tuple[float, ...]
    has_positive_inf: bool


@dataclass(frozen=True)
class MetricPoint:
    name: str
    kind: str
    unit: str
    attributes: tuple[Attribute, ...]
    resource: Resource
    source: str
    timestamp: str
    value: float | None = None
    histogram: Histogram | None = None
    exemplars: tuple[Exemplar, ...] = ()
    temporality: str = "unspecified"
    monotonic: bool | None = None

    @property
    def identity(self) -> str:
        pairs = ",".join(
            f"{item.key}={item.value}" for item in sorted(self.attributes, key=lambda a: a.key)
        )
        return f"{self.resource.identity}|{self.name}|{pairs}|{self.timestamp}"

    @property
    def number(self) -> float | None:
        if self.kind == "histogram":
            return self.histogram.count if self.histogram is not None else None
        return self.value


@dataclass(frozen=True)
class Finding:
    rule_id: str
    level: Literal["error", "warning"]
    message: str
    source: str
    evidence: tuple[tuple[str, str], ...] = ()
    suppressed: bool = False
    suppression_reason: str = ""

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            [self.rule_id, self.level, self.message, self.source, list(self.evidence)],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def with_suppression(self, reason: str) -> Finding:
        return Finding(
            rule_id=self.rule_id,
            level=self.level,
            message=self.message,
            source=self.source,
            evidence=self.evidence,
            suppressed=True,
            suppression_reason=reason,
        )


@dataclass(frozen=True)
class Report:
    input_digest: str
    point_count: int
    resource_count: int
    findings: tuple[Finding, ...]

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.level == "error" and not f.suppressed)

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.level == "warning" and not f.suppressed)

    @property
    def suppressed_count(self) -> int:
        return sum(1 for f in self.findings if f.suppressed)

    def gate_failed(self, fail_on: str) -> bool:
        if fail_on == "none":
            return False
        if fail_on == "warning":
            return any(not f.suppressed for f in self.findings)
        return self.errors > 0

    @property
    def digest(self) -> str:
        payload = json.dumps(
            [
                self.input_digest,
                self.point_count,
                self.resource_count,
                [[f.rule_id, f.fingerprint, f.suppressed] for f in self.findings],
            ],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    short_description: str
    guidance: str
    default_level: str = "error"


def evidence_text(finding: Finding) -> str:
    return "; ".join(f"{key}={value}" for key, value in finding.evidence)


def value_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return type(value).__name__
