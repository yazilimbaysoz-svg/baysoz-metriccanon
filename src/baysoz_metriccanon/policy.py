"""Baysöz Labs <baysozlabs@proton.me> — versioned, deterministic policy loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .units import UnitFactor

POLICY_SCHEMA = "baysoz-metriccanon/policy-v1"

DEFAULT_CANONICAL_NAMES = {
    "http.server.duration": "http.server.request.duration",
    "http.client.duration": "http.client.request.duration",
    "http.active_requests": "http.server.active_requests",
    "http.request.size": "http.request.body.size",
    "http.response.size": "http.response.body.size",
}

DEFAULT_CANONICAL_ATTRIBUTES = {
    "http.method": "http.request.method",
    "http.status_code": "http.response.status_code",
    "http.url": "url.full",
    "http.target": "url.path",
    "net.peer.name": "server.address",
    "net.peer.port": "server.port",
}

DEFAULT_ALIASES = {
    "second": "s",
    "seconds": "s",
    "byte": "By",
    "bytes": "By",
    "millisecond": "ms",
    "milliseconds": "ms",
    "microsecond": "us",
    "microseconds": "us",
    "nanosecond": "ns",
    "nanoseconds": "ns",
    "minute": "min",
    "minutes": "min",
    "hour": "h",
    "hours": "h",
    "day": "d",
    "days": "d",
    "kilobyte": "kB",
    "megabyte": "MB",
    "gigabyte": "GB",
    "kibibyte": "KiBy",
    "mebibyte": "MiBy",
    "gibibyte": "GiBy",
    "scalar": "1",
    "dimensionless": "1",
    "percent": "%",
}

DEFAULT_FACTOR_SPECS = {
    "ms": ("s", "0.001"),
    "us": ("s", "0.000001"),
    "ns": ("s", "0.000000001"),
    "min": ("s", "60"),
    "h": ("s", "3600"),
    "d": ("s", "86400"),
    "kB": ("By", "1000"),
    "MB": ("By", "1000000"),
    "GB": ("By", "1000000000"),
    "KiBy": ("By", "1024"),
    "MiBy": ("By", "1048576"),
    "GiBy": ("By", "1073741824"),
}

DEFAULT_FACTORS = {
    key: UnitFactor(base=base, factor=Decimal(value))
    for key, (base, value) in DEFAULT_FACTOR_SPECS.items()
}


@dataclass(frozen=True)
class Policy:
    canonical_names: dict[str, str]
    canonical_attributes: dict[str, str]
    unit_aliases: dict[str, str]
    unit_factors: dict[str, UnitFactor]
    prometheus_units: dict[str, str]
    source: str

    @property
    def digest(self) -> str:
        import hashlib

        payload = json.dumps(
            [
                sorted(self.canonical_names.items()),
                sorted(self.canonical_attributes.items()),
                sorted(self.unit_aliases.items()),
                sorted((k, v.base, str(v.factor)) for k, v in self.unit_factors.items()),
                sorted(self.prometheus_units.items()),
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PolicyError(ValueError):
    pass


def default_policy() -> Policy:
    return Policy(
        canonical_names=dict(DEFAULT_CANONICAL_NAMES),
        canonical_attributes=dict(DEFAULT_CANONICAL_ATTRIBUTES),
        unit_aliases=dict(DEFAULT_ALIASES),
        unit_factors=dict(DEFAULT_FACTORS),
        prometheus_units={},
        source="built-in",
    )


DEFAULT_POLICY = default_policy()


def _string_map(raw: Any, label: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise PolicyError(f"{label} must be a JSON object")
    result: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise PolicyError(f"{label} keys must be non-empty strings")
        if not isinstance(value, str) or not value:
            raise PolicyError(f"{label}[{key}] must be a non-empty string")
        result[key] = value
    return result


def load_policy(path: str | None = None) -> Policy:
    policy = default_policy()
    if path is None:
        return policy
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot read policy {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PolicyError("policy root must be a JSON object")
    if raw.get("schema") != POLICY_SCHEMA:
        raise PolicyError(f"policy schema must be {POLICY_SCHEMA}")
    allowed = {
        "schema",
        "attribution",
        "canonical_names",
        "canonical_attributes",
        "unit_aliases",
        "unit_factors",
        "prometheus_units",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise PolicyError(f"unknown policy keys: {', '.join(unknown)}")
    if "attribution" in raw and "baysozlabs@proton.me" not in str(raw["attribution"]):
        raise PolicyError("policy attribution must name Baysöz Labs <baysozlabs@proton.me>")
    if "canonical_names" in raw:
        policy.canonical_names.update(_string_map(raw["canonical_names"], "canonical_names"))
    if "canonical_attributes" in raw:
        policy.canonical_attributes.update(
            _string_map(raw["canonical_attributes"], "canonical_attributes")
        )
    if "unit_aliases" in raw:
        policy.unit_aliases.update(_string_map(raw["unit_aliases"], "unit_aliases"))
    if "prometheus_units" in raw:
        policy.prometheus_units.update(_string_map(raw["prometheus_units"], "prometheus_units"))
    if "unit_factors" in raw:
        factors = raw["unit_factors"]
        if not isinstance(factors, dict):
            raise PolicyError("unit_factors must be a JSON object")
        for key, spec in factors.items():
            if not isinstance(key, str) or not key:
                raise PolicyError("unit_factors keys must be non-empty strings")
            if not isinstance(spec, dict) or set(spec) != {"base", "factor"}:
                raise PolicyError(f"unit_factors[{key}] requires exactly base and factor")
            base, factor = spec["base"], spec["factor"]
            if not isinstance(base, str) or not base:
                raise PolicyError(f"unit_factors[{key}].base must be a string")
            if isinstance(factor, bool) or not isinstance(factor, (str, int, float)):
                raise PolicyError(f"unit_factors[{key}].factor must be numeric")
            try:
                parsed = Decimal(str(factor))
            except InvalidOperation as exc:
                raise PolicyError(f"unit_factors[{key}].factor is invalid") from exc
            if not parsed.is_finite() or parsed <= 0:
                raise PolicyError(f"unit_factors[{key}].factor must be positive and finite")
            policy.unit_factors[key] = UnitFactor(base=base, factor=parsed)
    return Policy(
        canonical_names=policy.canonical_names,
        canonical_attributes=policy.canonical_attributes,
        unit_aliases=policy.unit_aliases,
        unit_factors=policy.unit_factors,
        prometheus_units=policy.prometheus_units,
        source=path,
    )
