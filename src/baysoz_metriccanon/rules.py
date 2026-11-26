"""Baysöz Labs <baysozlabs@proton.me> — deterministic semantic invariant engine."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Iterable

from .model import Finding, MetricPoint, Report, Rule
from .policy import Policy
from .units import normalize_unit

RULES = (
    Rule(
        "MC001",
        "MetricKindConflict",
        "One metric name is exported with more than one instrument kind",
        "A metric name must have a single instrument kind across all producers.",
    ),
    Rule(
        "MC002",
        "MetricUnitConflict",
        "One metric name is exported with incompatible canonical units",
        "Normalize units with policy aliases and factors before aggregation.",
    ),
    Rule(
        "MC003",
        "UnknownMetricUnit",
        "Metric unit is not in the built-in catalog or policy",
        "Declare the unit in policy.unit_aliases or policy.unit_factors.",
    ),
    Rule(
        "MC004",
        "CounterMonotonicityViolation",
        "Counter decreases or is declared non-monotonic",
        "Counters must be monotonic; delta counters must never be negative.",
    ),
    Rule(
        "MC005",
        "HistogramStructureViolation",
        "Histogram bounds or bucket counts violate the OTLP data model",
        "Use strictly increasing finite bounds and an implicit +Inf bucket.",
    ),
    Rule(
        "MC006",
        "AttributeTypeConflict",
        "One attribute key carries different value types",
        "Pin attribute value types; mixed types are dropped by several backends.",
    ),
    Rule(
        "MC007",
        "AttributeKeyCaseConflict",
        "Attribute keys collide after case folding or are duplicated",
        "Use one canonical spelling per attribute key.",
    ),
    Rule(
        "MC008",
        "DeprecatedMetricName",
        "Metric name is a deprecated semantic-convention spelling",
        "Migrate to the canonical name supplied in the finding.",
    ),
    Rule(
        "MC009",
        "DeprecatedAttributeName",
        "Attribute key is a deprecated semantic-convention spelling",
        "Migrate to the canonical attribute key supplied in the finding.",
    ),
    Rule(
        "MC010",
        "InvalidExemplarId",
        "Exemplar trace or span identifier is malformed",
        "Use 32-hex trace ids and 16-hex non-zero span ids.",
    ),
    Rule(
        "MC011",
        "MissingServiceIdentity",
        "Resource has no service.name attribute",
        "Attach service.name to every resource before export.",
    ),
    Rule(
        "MC012",
        "DuplicateSeries",
        "Identical metric series is exported more than once",
        "Deduplicate points before export; exact duplicates corrupt aggregations.",
    ),
    Rule(
        "MC013",
        "TemporalityConflict",
        "One metric name mixes cumulative and delta temporality",
        "Select one aggregation temporality per metric across the pipeline.",
    ),
    Rule(
        "MC014",
        "BaselineEntryStale",
        "Accepted baseline finding no longer matches the analyzed input",
        "Remove stale suppressions so the baseline stays auditable.",
        "warning",
    ),
    Rule(
        "MC015",
        "HistogramCountMismatch",
        "Histogram bucket total disagrees with the declared count",
        "Recompute bucket counts from raw observations.",
    ),
    Rule(
        "MC016",
        "NonFiniteMetricValue",
        "Metric value or histogram statistic is NaN or infinite",
        "Reject NaN and infinity at instrumentation boundaries.",
    ),
    Rule(
        "MC017",
        "MetricNameConventionViolation",
        "Metric name contains unsupported separators or characters",
        "Use lowercase dot- or underscore-separated ASCII identifiers.",
    ),
)

RULE_BY_ID = {rule.rule_id: rule for rule in RULES}
_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._][a-z0-9]+)*$")
_HEX_32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_HEX_16_RE = re.compile(r"^[0-9a-fA-F]{16}$")
_TOLERANCE = 1e-9


def _fmt(value: float | int) -> str:
    return format(float(value), ".12g")


def _finding(
    rule_id: str,
    message: str,
    source: str,
    evidence: Iterable[tuple[str, str]] = (),
) -> Finding:
    rule = RULE_BY_ID[rule_id]
    level: str = rule.default_level
    return Finding(
        rule_id=rule_id,
        level=level,  # type: ignore[arg-type]
        message=message,
        source=source,
        evidence=tuple(evidence),
    )


def _histogram_findings(point: MetricPoint) -> list[Finding]:
    histogram = point.histogram
    if histogram is None:
        return []
    findings: list[Finding] = []
    issues: list[str] = []
    if not histogram.has_positive_inf:
        issues.append("missing +Inf bucket")
    expected = len(histogram.bounds) + (1 if histogram.has_positive_inf else 0)
    if len(histogram.bucket_counts) != expected:
        issues.append(f"expected {expected} bucket counts, got {len(histogram.bucket_counts)}")
    previous: float | None = None
    for bound in histogram.bounds:
        if not math.isfinite(bound):
            issues.append("non-finite explicit bound")
        if previous is not None and bound <= previous:
            issues.append("bounds are not strictly increasing")
        previous = bound
    if any(not math.isfinite(count) or count < 0 for count in histogram.bucket_counts):
        issues.append("invalid bucket counts")
    if histogram.count is not None and (not math.isfinite(histogram.count) or histogram.count < 0):
        issues.append("invalid total count")
    if issues:
        findings.append(
            _finding(
                "MC005",
                f"histogram {point.name} has invalid structure: {'; '.join(sorted(set(issues)))}",
                point.source,
                (("service", point.resource.identity), ("issues", ",".join(sorted(set(issues))))),
            )
        )
    if histogram.count is None:
        findings.append(
            _finding(
                "MC015",
                f"histogram {point.name} has no declared count",
                point.source,
                (("service", point.resource.identity),),
            )
        )
    elif math.isfinite(histogram.count):
        bucket_total = sum(histogram.bucket_counts)
        if math.isfinite(bucket_total) and abs(bucket_total - histogram.count) > max(
            _TOLERANCE, abs(histogram.count) * _TOLERANCE
        ):
            findings.append(
                _finding(
                    "MC015",
                    f"histogram {point.name} bucket total {_fmt(bucket_total)} "
                    f"differs from count {_fmt(histogram.count)}",
                    point.source,
                    (
                        ("service", point.resource.identity),
                        ("bucket_total", _fmt(bucket_total)),
                        ("count", _fmt(histogram.count)),
                    ),
                )
            )
    if histogram.total is not None and not math.isfinite(histogram.total):
        findings.append(
            _finding(
                "MC016",
                f"histogram {point.name} has a non-finite sum",
                point.source,
                (("service", point.resource.identity), ("sum", str(histogram.total))),
            )
        )
    return findings


def _point_findings(point: MetricPoint, policy: Policy) -> list[Finding]:
    findings: list[Finding] = []
    unit = point.unit.strip()
    info = normalize_unit(point.unit, policy.unit_aliases, policy.unit_factors)
    if unit and not info.known:
        findings.append(
            _finding(
                "MC003",
                f"unit '{point.unit}' on metric {point.name} is not recognized",
                point.source,
                (("unit", point.unit), ("metric", point.name)),
            )
        )
    if not point.resource.service_name:
        findings.append(
            _finding(
                "MC011",
                f"resource for metric {point.name} has no service.name",
                point.source,
                (("metric", point.name),),
            )
        )
    if not _NAME_RE.fullmatch(point.name):
        findings.append(
            _finding(
                "MC017",
                f"metric name '{point.name}' violates the lowercase identifier convention",
                point.source,
                (("name", point.name),),
            )
        )
    replacement = policy.canonical_names.get(point.name)
    if replacement is not None:
        findings.append(
            _finding(
                "MC008",
                f"metric {point.name} uses a deprecated name; use {replacement}",
                point.source,
                (("deprecated", point.name), ("replacement", replacement)),
            )
        )
    local_types: dict[str, set[str]] = defaultdict(set)
    local_keys: dict[str, set[str]] = defaultdict(set)
    for attribute in point.attributes:
        local_types[attribute.key].add(attribute.type_name)
        local_keys[attribute.key.lower()].add(attribute.key)
        attr_replacement = policy.canonical_attributes.get(attribute.key)
        if attr_replacement is not None:
            findings.append(
                _finding(
                    "MC009",
                    f"attribute {attribute.key} is deprecated; use {attr_replacement}",
                    attribute.source,
                    (("deprecated", attribute.key), ("replacement", attr_replacement)),
                )
            )
    for key, types in sorted(local_types.items()):
        if len(types) > 1:
            findings.append(
                _finding(
                    "MC006",
                    f"attribute {key} has conflicting value types: {', '.join(sorted(types))}",
                    point.source,
                    (("attribute", key), ("types", ",".join(sorted(types)))),
                )
            )
    for folded, keys in sorted(local_keys.items()):
        if len(keys) > 1:
            findings.append(
                _finding(
                    "MC007",
                    f"attribute keys collide after case folding: {', '.join(sorted(keys))}",
                    point.source,
                    (("folded", folded), ("keys", ",".join(sorted(keys)))),
                )
            )
    if point.value is not None and not math.isfinite(point.value):
        findings.append(
            _finding(
                "MC016",
                f"metric {point.name} has a non-finite value: {point.value}",
                point.source,
                (("metric", point.name), ("value", str(point.value))),
            )
        )
    for exemplar in point.exemplars:
        trace_valid = bool(_HEX_32_RE.fullmatch(exemplar.trace_id)) and any(
            char != "0" for char in exemplar.trace_id
        )
        span_valid = bool(_HEX_16_RE.fullmatch(exemplar.span_id)) and any(
            char != "0" for char in exemplar.span_id
        )
        if not trace_valid or not span_valid:
            findings.append(
                _finding(
                    "MC010",
                    f"exemplar on {point.name} has an invalid trace or span id",
                    exemplar.source,
                    (
                        ("trace_id", exemplar.trace_id or "<missing>"),
                        ("span_id", exemplar.span_id or "<missing>"),
                    ),
                )
            )
    if point.monotonic is False and point.kind == "counter":
        findings.append(
            _finding(
                "MC004",
                f"counter {point.name} is explicitly declared non-monotonic",
                point.source,
                (("counter", point.name), ("service", point.resource.identity)),
            )
        )
    findings.extend(_histogram_findings(point))
    return findings


def _series_key(point: MetricPoint) -> tuple[str, str, str, str, tuple[tuple[str, str], ...]]:
    attrs = tuple(sorted((a.key, f"{a.type_name}:{a.value}") for a in point.attributes))
    return (
        point.name,
        point.resource.identity,
        point.kind,
        point.temporality,
        attrs,
    )


def analyze(points: list[MetricPoint], policy: Policy, input_digest: str) -> Report:
    findings: list[Finding] = []
    findings.extend(finding for point in points for finding in _point_findings(point, policy))
    name_points: dict[str, list[MetricPoint]] = defaultdict(list)
    attr_types: dict[str, set[str]] = defaultdict(set)
    attr_case: dict[str, set[str]] = defaultdict(set)
    series: dict[tuple[str, str, str, str, tuple[tuple[str, str], ...]], list[MetricPoint]] = (
        defaultdict(list)
    )
    for point in points:
        name_points[point.name].append(point)
        for attribute in point.attributes:
            attr_types[attribute.key].add(attribute.type_name)
            attr_case[attribute.key.lower()].add(attribute.key)
        series[_series_key(point)].append(point)
    for name, group in sorted(name_points.items()):
        kinds = sorted({p.kind for p in group})
        if len(kinds) > 1:
            findings.append(
                _finding(
                    "MC001",
                    f"metric {name} has conflicting kinds: {', '.join(kinds)}",
                    sorted(p.source for p in group)[0],
                    (("metric", name), ("kinds", ",".join(kinds))),
                )
            )
        infos = [normalize_unit(p.unit, policy.unit_aliases, policy.unit_factors) for p in group]
        known = [info for info in infos if info.comparable]
        bases = sorted({info.base for info in known})
        if len(bases) > 1:
            units = sorted({p.unit.strip() for p in group if p.unit.strip()})
            findings.append(
                _finding(
                    "MC002",
                    f"metric {name} uses incompatible units: {', '.join(units)}",
                    sorted(p.source for p in group)[0],
                    (("metric", name), ("units", ",".join(units)), ("canonical", ",".join(bases))),
                )
            )
        temporalities = sorted({p.temporality for p in group if p.kind == "counter"})
        if {"cumulative", "delta"}.issubset(set(temporalities)):
            findings.append(
                _finding(
                    "MC013",
                    f"counter {name} mixes cumulative and delta temporality",
                    sorted(p.source for p in group)[0],
                    (("counter", name), ("temporalities", ",".join(temporalities))),
                )
            )
    for key, types in sorted(attr_types.items()):
        if len(types) > 1:
            findings.append(
                _finding(
                    "MC006",
                    f"attribute {key} has conflicting value types: {', '.join(sorted(types))}",
                    "global",
                    (("attribute", key), ("types", ",".join(sorted(types)))),
                )
            )
    for folded, keys in sorted(attr_case.items()):
        if len(keys) > 1:
            findings.append(
                _finding(
                    "MC007",
                    f"attribute keys collide after case folding: {', '.join(sorted(keys))}",
                    "global",
                    (("folded", folded), ("keys", ",".join(sorted(keys)))),
                )
            )
    for key, group in sorted(series.items()):
        by_timestamp: dict[str, list[MetricPoint]] = defaultdict(list)
        for point in group:
            by_timestamp[point.timestamp].append(point)
        for timestamp, exact in sorted(by_timestamp.items()):
            if len(exact) > 1:
                findings.append(
                    _finding(
                        "MC012",
                        f"series {key[0]} has {len(exact)} identical points at '{timestamp}'",
                        sorted(p.source for p in exact)[0],
                        (
                            ("metric", key[0]),
                            ("service", key[1]),
                            ("count", str(len(exact))),
                        ),
                    )
                )
        if key[2] != "counter" or key[3] not in {"cumulative", "delta"}:
            continue
        ordered = sorted(group, key=lambda p: (p.timestamp, p.source))
        previous: MetricPoint | None = None
        for current in ordered:
            number = current.number
            if number is None or not math.isfinite(number):
                continue
            if key[3] == "cumulative" and previous is not None:
                old = previous.number
                if old is not None and number < old - _TOLERANCE:
                    findings.append(
                        _finding(
                            "MC004",
                            f"cumulative counter {key[0]} decreased from {_fmt(old)} "
                            f"to {_fmt(number)}",
                            current.source,
                            (
                                ("counter", key[0]),
                                ("service", key[1]),
                                ("previous", _fmt(old)),
                                ("current", _fmt(number)),
                            ),
                        )
                    )
            if key[3] == "delta" and number < -_TOLERANCE:
                findings.append(
                    _finding(
                        "MC004",
                        f"delta counter {key[0]} has negative value {_fmt(number)}",
                        current.source,
                        (("counter", key[0]), ("service", key[1]), ("value", _fmt(number))),
                    )
                )
            previous = current
    ordered = sorted(findings, key=lambda f: (f.rule_id, f.source, f.message, f.fingerprint))
    resources = {p.resource.service_name or "unknown-service" for p in points}
    return Report(
        input_digest=input_digest,
        point_count=len(points),
        resource_count=len(resources),
        findings=tuple(ordered),
    )
