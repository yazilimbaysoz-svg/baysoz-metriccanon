"""Baysöz Labs <baysozlabs@proton.me> — strict OTLP/prometheus/canonical input normalization."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import Attribute, Exemplar, Histogram, MetricPoint, Resource
from .policy import Policy

SNAPSHOT_SCHEMA = "baysoz-metriccanon/v1"
_KINDS = frozenset({"counter", "gauge", "histogram"})
_TEMPORALITIES = frozenset({"cumulative", "delta", "unspecified"})
_SAMPLE_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+(\S+)(?:\s+(\d+))?\s*$")
_LABEL_KEY_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


class InputError(ValueError):
    pass


def read_input(path: str) -> tuple[bytes, str]:
    import hashlib

    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read input {path}: {exc}") from exc
    return raw, hashlib.sha256(raw).hexdigest()


def parse_input(
    raw: bytes, source: str, policy: Policy
) -> tuple[list[MetricPoint], frozenset[str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"input is not valid UTF-8: {exc}") from exc
    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return parse_prometheus(text, source, policy)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise InputError("JSON input root must be an object")
    if data.get("schema") == SNAPSHOT_SCHEMA:
        return parse_canonical(data, source)
    if "resourceMetrics" in data:
        return parse_otlp(data, source)
    raise InputError(
        "unrecognized JSON input: expected schema 'baysoz-metriccanon/v1' or 'resourceMetrics'"
    )


def _attributes(raw: Any, source: str) -> tuple[Attribute, ...]:
    if raw is None:
        return ()
    if isinstance(raw, dict):
        pairs = list(raw.items())
    elif isinstance(raw, list):
        pairs = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or set(item) != {"key", "value"}:
                raise InputError(f"{source}: attribute[{index}] requires exactly key and value")
            pairs.append((item["key"], item["value"]))
    else:
        raise InputError(f"{source}: attributes must be an object or a list")
    result: list[Attribute] = []
    for key, value in pairs:
        if not isinstance(key, str) or not key:
            raise InputError(f"{source}: attribute key must be a non-empty string")
        if isinstance(value, (dict, list)) or value is None:
            raise InputError(f"{source}: attribute {key} has an unsupported value")
        result.append(Attribute(key=key, value=value, source=source))
    return tuple(result)


def _number(value: Any, source: str, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{source}: {label} must be numeric")
    return float(value)


def _integer(value: Any, source: str, label: str) -> int:
    if isinstance(value, bool):
        raise InputError(f"{source}: {label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise InputError(f"{source}: {label} must be an integer") from exc
    raise InputError(f"{source}: {label} must be an integer")


def _timestamp_from_nanos(raw: Any, source: str) -> str:
    if raw is None:
        return ""
    nanos = _integer(raw, source, "timeUnixNano")
    seconds, remainder = divmod(nanos, 1_000_000_000)
    try:
        stamp = datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except (OSError, OverflowError, ValueError) as exc:
        raise InputError(f"{source}: timeUnixNano is outside the supported range") from exc
    return f"{stamp}.{remainder:09d}Z"


def _exemplars(raw: Any, source: str) -> tuple[Exemplar, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise InputError(f"{source}: exemplars must be a list")
    result: list[Exemplar] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise InputError(f"{source}: exemplars[{index}] must be an object")
        trace = item.get("trace_id", item.get("traceId", ""))
        span = item.get("span_id", item.get("spanId", ""))
        if not isinstance(trace, str) or not isinstance(span, str):
            raise InputError(f"{source}: exemplars[{index}] ids must be strings")
        result.append(Exemplar(trace, span, f"{source}:exemplars[{index}]"))
    return tuple(result)


def _histogram(raw: Any, source: str) -> Histogram:
    if not isinstance(raw, dict):
        raise InputError(f"{source}: histogram must be an object")
    bounds_raw = raw.get("bounds", raw.get("explicitBounds", []))
    counts_raw = raw.get("bucket_counts", raw.get("bucketCounts", []))
    if not isinstance(bounds_raw, list) or not isinstance(counts_raw, list):
        raise InputError(f"{source}: histogram bounds and bucket_counts must be lists")
    bounds = tuple(_number(item, source, "histogram bound") for item in bounds_raw)
    counts = tuple(_number(item, source, "histogram bucket count") for item in counts_raw)
    count = raw.get("count")
    total = raw.get("sum")
    has_inf = raw.get("has_positive_inf", True)
    if count is not None:
        count = _number(count, source, "histogram count")
    if total is not None:
        total = _number(total, source, "histogram sum")
    if not isinstance(has_inf, bool):
        raise InputError(f"{source}: histogram has_positive_inf must be a boolean")
    return Histogram(count, total, bounds, counts, has_inf)


def parse_canonical(data: dict[str, Any], source: str) -> tuple[list[MetricPoint], frozenset[str]]:
    points_raw = data.get("points")
    if not isinstance(points_raw, list):
        raise InputError(f"{source}: canonical input requires a points list")
    services_raw = data.get("services", {})
    if not isinstance(services_raw, dict):
        raise InputError(f"{source}: services must be an object")
    default_service = data.get("service")
    default_name: str | None = None
    default_attrs: tuple[Attribute, ...] = ()
    if default_service is not None:
        if not isinstance(default_service, dict):
            raise InputError(f"{source}: service must be an object")
        default_name = default_service.get("name")
        if default_name is not None and not isinstance(default_name, str):
            raise InputError(f"{source}: service.name must be a string")
        default_attrs = _attributes(default_service.get("attributes"), f"{source}:service")
    resources: dict[str, Resource] = {}
    if default_name:
        resources[default_name] = Resource(default_name, default_attrs, f"{source}:service")
    for name, attrs_raw in services_raw.items():
        if not isinstance(name, str) or not name:
            raise InputError(f"{source}: service names must be non-empty strings")
        resources[name] = Resource(
            name, _attributes(attrs_raw, f"{source}:services[{name}]"), source
        )
    points: list[MetricPoint] = []
    point_resources: set[str] = set()
    for index, item in enumerate(points_raw):
        where = f"{source}:points[{index}]"
        if not isinstance(item, dict):
            raise InputError(f"{where}: point must be an object")
        name = item.get("name")
        kind = item.get("kind")
        if not isinstance(name, str) or not name:
            raise InputError(f"{where}: name must be a non-empty string")
        if kind not in _KINDS:
            raise InputError(f"{where}: kind must be one of {', '.join(sorted(_KINDS))}")
        selected = item.get("service", default_name)
        if selected is not None and not isinstance(selected, str):
            raise InputError(f"{where}: service must be a string")
        resource_attrs = default_attrs
        if selected in resources:
            resource = resources[selected]
        else:
            override = item.get("resource")
            override_attrs = (
                _attributes(override, where) if override is not None else resource_attrs
            )
            service_name = selected
            if isinstance(override, dict) and "service.name" in override:
                service_name = override["service.name"]
                if not isinstance(service_name, str):
                    raise InputError(f"{where}: resource service.name must be a string")
            resource = Resource(service_name, override_attrs, where)
        unit = item.get("unit", "")
        if not isinstance(unit, str):
            raise InputError(f"{where}: unit must be a string")
        timestamp = item.get("timestamp", "")
        if timestamp is None:
            timestamp = ""
        if not isinstance(timestamp, str):
            raise InputError(f"{where}: timestamp must be a string")
        temporality = item.get("temporality", "cumulative" if kind == "counter" else "unspecified")
        if temporality not in _TEMPORALITIES:
            raise InputError(
                f"{where}: temporality must be one of {', '.join(sorted(_TEMPORALITIES))}"
            )
        monotonic = item.get("monotonic")
        if monotonic is not None and not isinstance(monotonic, bool):
            raise InputError(f"{where}: monotonic must be a boolean")
        value = None
        histogram = None
        if kind == "histogram":
            histogram = _histogram(item.get("histogram"), where)
        else:
            if "value" not in item:
                raise InputError(f"{where}: numeric value is required")
            value = _number(item["value"], where, "value")
        point_resources.add(resource.service_name or "unknown-service")
        points.append(
            MetricPoint(
                name=name,
                kind=kind,
                unit=unit,
                attributes=_attributes(item.get("attributes"), where),
                resource=resource,
                source=where,
                timestamp=timestamp,
                value=value,
                histogram=histogram,
                exemplars=_exemplars(item.get("exemplars"), where),
                temporality=temporality,
                monotonic=monotonic,
            )
        )
    return points, frozenset(point_resources)


def _otlp_value(raw: Any, source: str) -> str | int | float | bool:
    if not isinstance(raw, dict):
        raise InputError(f"{source}: OTLP value must be an object")
    if "stringValue" in raw:
        value = raw["stringValue"]
        if not isinstance(value, str):
            raise InputError(f"{source}: stringValue must be a string")
        return value
    if "intValue" in raw:
        return _integer(raw["intValue"], source, "intValue")
    if "doubleValue" in raw:
        return _number(raw["doubleValue"], source, "doubleValue")
    if "boolValue" in raw:
        value = raw["boolValue"]
        if not isinstance(value, bool):
            raise InputError(f"{source}: boolValue must be a boolean")
        return value
    raise InputError(f"{source}: unsupported OTLP value keys: {', '.join(sorted(raw)) or 'none'}")


def _otlp_attributes(raw: Any, source: str) -> tuple[Attribute, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise InputError(f"{source}: OTLP attributes must be a list")
    result: list[Attribute] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or "key" not in item or "value" not in item:
            raise InputError(f"{source}: OTLP attribute[{index}] requires key and value")
        key = item["key"]
        if not isinstance(key, str) or not key:
            raise InputError(f"{source}: OTLP attribute key must be non-empty")
        result.append(Attribute(key, _otlp_value(item["value"], f"{source}:attr[{index}]"), source))
    return tuple(result)


def _otlp_number(raw: dict[str, Any], source: str) -> float:
    has_double = "asDouble" in raw
    has_int = "asInt" in raw
    if has_double and has_int:
        raise InputError(f"{source}: data point has both asDouble and asInt")
    if has_double:
        return _number(raw["asDouble"], source, "asDouble")
    if has_int:
        return float(_integer(raw["asInt"], source, "asInt"))
    raise InputError(f"{source}: data point requires asDouble or asInt")


def parse_otlp(data: dict[str, Any], source: str) -> tuple[list[MetricPoint], frozenset[str]]:
    resource_metrics = data.get("resourceMetrics")
    if not isinstance(resource_metrics, list):
        raise InputError(f"{source}: resourceMetrics must be a list")
    points: list[MetricPoint] = []
    resources: set[str] = set()
    for r_index, resource_metric in enumerate(resource_metrics):
        if not isinstance(resource_metric, dict):
            raise InputError(f"{source}: resourceMetrics[{r_index}] must be an object")
        resource_raw = resource_metric.get("resource", {})
        if not isinstance(resource_raw, dict):
            raise InputError(f"{source}: resourceMetrics[{r_index}].resource must be an object")
        attrs = _otlp_attributes(resource_raw.get("attributes"), f"{source}:resource[{r_index}]")
        service_name = next((a.value for a in attrs if a.key == "service.name"), None)
        if service_name is not None and not isinstance(service_name, str):
            raise InputError(f"{source}: resource service.name must be a string")
        resource = Resource(service_name, attrs, f"{source}:resource[{r_index}]")
        resources.add(service_name or "unknown-service")
        scopes = resource_metric.get("scopeMetrics", [])
        if not isinstance(scopes, list):
            raise InputError(f"{source}: scopeMetrics must be a list")
        for s_index, scope in enumerate(scopes):
            if not isinstance(scope, dict) or not isinstance(scope.get("metrics", []), list):
                raise InputError(f"{source}: scopeMetrics[{s_index}] must contain a metrics list")
            for m_index, metric in enumerate(scope["metrics"]):
                where = f"{source}:resource[{r_index}]/scope[{s_index}]/metrics[{m_index}]"
                if not isinstance(metric, dict) or not isinstance(metric.get("name"), str):
                    raise InputError(f"{where}: metric name is required")
                name = metric["name"]
                unit = metric.get("unit", "")
                if not isinstance(unit, str):
                    raise InputError(f"{where}: unit must be a string")
                kinds = [key for key in ("sum", "gauge", "histogram") if key in metric]
                if len(kinds) != 1:
                    raise InputError(
                        f"{where}: metric must contain exactly one of sum, gauge, histogram"
                    )
                flavor = kinds[0]
                spec = metric[flavor]
                if not isinstance(spec, dict):
                    raise InputError(f"{where}: {flavor} must be an object")
                kind = "counter" if flavor == "sum" else flavor
                temporality = "unspecified"
                monotonic: bool | None = None
                if flavor == "sum":
                    mapping = {1: "delta", 2: "cumulative"}
                    temporality = mapping.get(spec.get("aggregationTemporality"), "unspecified")
                    if "isMonotonic" in spec:
                        if not isinstance(spec["isMonotonic"], bool):
                            raise InputError(f"{where}: isMonotonic must be a boolean")
                        monotonic = spec["isMonotonic"]
                data_points = spec.get("dataPoints", [])
                if not isinstance(data_points, list):
                    raise InputError(f"{where}: dataPoints must be a list")
                for d_index, point in enumerate(data_points):
                    point_where = f"{where}/dataPoints[{d_index}]"
                    if not isinstance(point, dict):
                        raise InputError(f"{point_where}: data point must be an object")
                    value = None
                    histogram = None
                    if flavor == "histogram":
                        bounds = point.get("explicitBounds", [])
                        counts = point.get("bucketCounts", [])
                        if not isinstance(bounds, list) or not isinstance(counts, list):
                            raise InputError(f"{point_where}: bounds and counts must be lists")
                        total = point.get("sum")
                        if total is not None:
                            total = _number(total, point_where, "histogram sum")
                        raw_count = point.get("count")
                        count = (
                            None
                            if raw_count is None
                            else _number(
                                _integer(raw_count, point_where, "count"), point_where, "count"
                            )
                        )
                        histogram = Histogram(
                            count=count,
                            total=total,
                            bounds=tuple(
                                _number(item, point_where, "explicitBound") for item in bounds
                            ),
                            bucket_counts=tuple(
                                _number(
                                    _integer(item, point_where, "bucketCount"),
                                    point_where,
                                    "bucketCount",
                                )
                                for item in counts
                            ),
                            has_positive_inf=True,
                        )
                    else:
                        value = _otlp_number(point, point_where)
                    points.append(
                        MetricPoint(
                            name=name,
                            kind=kind,
                            unit=unit,
                            attributes=_otlp_attributes(point.get("attributes"), point_where),
                            resource=resource,
                            source=point_where,
                            timestamp=_timestamp_from_nanos(point.get("timeUnixNano"), point_where),
                            value=value,
                            histogram=histogram,
                            exemplars=_exemplars(point.get("exemplars"), point_where),
                            temporality=temporality,
                            monotonic=monotonic,
                        )
                    )
    return points, frozenset(resources)


def _parse_label_text(raw: str, source: str) -> tuple[Attribute, ...]:
    result: list[Attribute] = []
    index = 0
    while index < len(raw):
        while index < len(raw) and raw[index] in " \t,":
            index += 1
        if index >= len(raw):
            break
        match = _LABEL_KEY_RE.match(raw, index)
        if match is None:
            raise InputError(f"{source}: malformed Prometheus label name")
        key = match.group()
        index = match.end()
        while index < len(raw) and raw[index] in " \t":
            index += 1
        if index >= len(raw) or raw[index] != "=":
            raise InputError(f"{source}: label {key} requires '='")
        index += 1
        while index < len(raw) and raw[index] in " \t":
            index += 1
        if index >= len(raw) or raw[index] != '"':
            raise InputError(f"{source}: label {key} requires a quoted value")
        index += 1
        chars: list[str] = []
        closed = False
        escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}
        while index < len(raw):
            char = raw[index]
            if char == "\\":
                index += 1
                if index >= len(raw) or raw[index] not in escapes:
                    raise InputError(f"{source}: unsupported escape in label {key}")
                chars.append(escapes[raw[index]])
                index += 1
            elif char == '"':
                index += 1
                closed = True
                break
            else:
                chars.append(char)
                index += 1
        if not closed:
            raise InputError(f"{source}: unterminated label {key}")
        result.append(Attribute(key, "".join(chars), source))
        while index < len(raw) and raw[index] in " \t":
            index += 1
        if index < len(raw) and raw[index] != ",":
            raise InputError(f"{source}: expected ',' after label {key}")
    return tuple(result)


def _resource_from_labels(attrs: tuple[Attribute, ...], source: str) -> Resource:
    name = None
    for key in ("service", "service_name", "job"):
        found = next((a.value for a in attrs if a.key == key), None)
        if isinstance(found, str) and found:
            name = found
            break
    return Resource(name, attrs, source)


def parse_prometheus(
    text: str, source: str, policy: Policy
) -> tuple[list[MetricPoint], frozenset[str]]:
    types: dict[str, str] = {}
    samples: list[tuple[str, tuple[Attribute, ...], float, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        where = f"{source}:line[{number}]"
        if stripped.startswith("#"):
            parts = stripped.split()
            if len(parts) >= 4 and parts[1] == "TYPE":
                if parts[3] not in _KINDS:
                    raise InputError(f"{where}: unsupported Prometheus type {parts[3]}")
                types[parts[2]] = parts[3]
            continue
        match = _SAMPLE_RE.fullmatch(stripped)
        if match is None:
            raise InputError(f"{where}: malformed Prometheus sample")
        name, label_text, raw_value, _timestamp = match.groups()
        attrs = _parse_label_text(label_text, where) if label_text is not None else ()
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise InputError(f"{where}: sample value is not numeric") from exc
        samples.append((name, attrs, value, where))
    points: list[MetricPoint] = []
    resources: set[str] = set()
    grouped: dict[
        tuple[str, tuple[tuple[str, str], ...]],
        dict[str, Any],
    ] = {}
    for name, attrs, value, where in samples:
        kind = types.get(name)
        if kind is None:
            for suffix in ("_bucket", "_sum", "_count"):
                if name.endswith(suffix) and types.get(name[: -len(suffix)]) == "histogram":
                    kind = "histogram"
                    break
        if kind is None:
            raise InputError(f"{where}: missing TYPE declaration for {name}")
        if kind != "histogram":
            resource = _resource_from_labels(attrs, where)
            resources.add(resource.service_name or "unknown-service")
            points.append(
                MetricPoint(
                    name=name,
                    kind=kind,
                    unit=policy.prometheus_units.get(name, ""),
                    attributes=attrs,
                    resource=resource,
                    source=where,
                    timestamp="",
                    value=value,
                )
            )
            continue
        suffix = "_bucket"
        if name.endswith(suffix):
            base = name[: -len(suffix)]
            le_attr = next((a for a in attrs if a.key == "le"), None)
            if le_attr is None or not isinstance(le_attr.value, str):
                raise InputError(f"{where}: histogram bucket requires a quoted le label")
            key_attrs = tuple(
                (a.key, a.value) for a in attrs if a.key != "le" and isinstance(a.value, str)
            )
            group = grouped.setdefault(
                (base, key_attrs),
                {
                    "entries": [],
                    "inf": None,
                    "sum": None,
                    "count": None,
                    "attrs": tuple(Attribute(key, value, where) for key, value in key_attrs),
                },
            )
            if le_attr.value == "+Inf":
                group["inf"] = (value, where)
            else:
                try:
                    le = float(le_attr.value)
                except ValueError as exc:
                    raise InputError(f"{where}: le must be numeric or +Inf") from exc
                group["entries"].append((le, value, where))
        elif name.endswith("_sum") or name.endswith("_count"):
            base = name.rsplit("_", 1)[0]
            key_attrs = tuple((a.key, a.value) for a in attrs if isinstance(a.value, str))
            group = grouped.setdefault(
                (base, key_attrs),
                {
                    "entries": [],
                    "inf": None,
                    "sum": None,
                    "count": None,
                    "attrs": tuple(Attribute(key, value, where) for key, value in key_attrs),
                },
            )
            group["sum" if name.endswith("_sum") else "count"] = (value, where)
        else:
            raise InputError(f"{where}: histogram sample must use _bucket, _sum or _count")
    for (base, _key_attrs), group in grouped.items():
        entries = sorted(group["entries"], key=lambda item: item[0])
        bounds = tuple(item[0] for item in entries)
        counts: list[float] = []
        previous = 0.0
        for _le, cumulative, _where in entries:
            counts.append(cumulative - previous)
            previous = cumulative
        inf = group["inf"]
        if inf is not None:
            counts.append(inf[0] - previous)
        attrs = group["attrs"]
        resource = _resource_from_labels(attrs, source)
        resources.add(resource.service_name or "unknown-service")
        points.append(
            MetricPoint(
                name=base,
                kind="histogram",
                unit=policy.prometheus_units.get(base, ""),
                attributes=attrs,
                resource=resource,
                source=f"{source}:histogram[{base}]",
                timestamp="",
                histogram=Histogram(
                    count=group["count"][0] if group["count"] is not None else None,
                    total=group["sum"][0] if group["sum"] is not None else None,
                    bounds=bounds,
                    bucket_counts=tuple(counts),
                    has_positive_inf=inf is not None,
                ),
            )
        )
    return points, frozenset(resources)
