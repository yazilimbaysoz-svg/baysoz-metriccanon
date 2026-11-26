"""Baysöz Labs <baysozlabs@proton.me> — normalization and strict-parser tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from baysoz_metriccanon import (
    InputError,
    PolicyError,
    default_policy,
    load_policy,
    parse_input,
    read_input,
)

FIXTURES = Path(__file__).parent / "fixtures"


def parse(name: str, policy=None):
    raw, digest = read_input(str(FIXTURES / name))
    points, services = parse_input(raw, name, policy or default_policy())
    return points, services, digest


def test_canonical_snapshot_is_normalized_losslessly():
    points, services, digest = parse("clean.snapshot.json")
    raw = (FIXTURES / "clean.snapshot.json").read_bytes()
    assert digest == hashlib.sha256(raw).hexdigest()
    assert services == frozenset({"checkout"})
    assert len(points) == 4
    assert points[0].kind == "histogram"
    assert points[0].exemplars[0].span_id == "00f067aa0ba902b7"
    assert points[0].resource.service_name == "checkout"
    assert points[3].value == 12


def test_otlp_json_shape_is_supported():
    points, services, digest = parse("adversarial.otlp.json")
    assert services == frozenset({"payments"})
    assert len(digest) == 64
    assert [p.kind for p in points] == ["histogram", "counter", "counter"]
    assert points[0].timestamp == "2026-11-26T00:00:00.000000000Z"
    assert points[0].histogram is not None
    assert points[0].histogram.bucket_counts == (1, 2)
    assert points[2].value == 8


def test_prometheus_exposition_builds_histogram_from_bucket_deltas():
    policy = load_policy(str(FIXTURES / "policy.json"))
    points, services, _digest = parse("prometheus.txt", policy)
    assert services == frozenset({"edge"})
    assert len(points) == 2
    histogram = next(point for point in points if point.name == "http_server_requests_seconds")
    assert histogram.unit == "s"
    assert histogram.histogram is not None
    assert histogram.histogram.bounds == (0.1, 0.5)
    assert histogram.histogram.bucket_counts == (1, 2, 1)
    assert histogram.histogram.count == 4
    assert histogram.resource.service_name == "edge"
    assert "le" not in {attr.key for attr in histogram.attributes}


def test_prometheus_drift_is_preserved_for_the_oracle():
    points, _services, _digest = parse("prometheus.drift.txt")
    histogram = next(point for point in points if point.name == "request_duration_seconds")
    assert histogram.histogram is not None
    assert histogram.histogram.bounds == (0.1, 0.2)
    assert histogram.histogram.bucket_counts == (5, -3)
    assert histogram.histogram.has_positive_inf is False


def test_unrecognized_json_is_rejected():
    with pytest.raises(InputError, match="unrecognized JSON input"):
        parse_input(b'{"hello": "world"}', "bad.json", default_policy())


def test_unsupported_prometheus_type_is_rejected():
    text = '# TYPE latency summary\nlatency{quantile="0.5"} 1\n'
    with pytest.raises(InputError, match="unsupported Prometheus type"):
        parse_input(text.encode(), "bad.txt", default_policy())


def test_malformed_labels_are_rejected():
    text = "# TYPE up gauge\nup{job=unquoted} 1\n"
    with pytest.raises(InputError, match="requires a quoted value"):
        parse_input(text.encode(), "bad.txt", default_policy())


def test_policy_rejects_unknown_keys(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps({"schema": "baysoz-metriccanon/policy-v1", "surprise": 1}), encoding="utf-8"
    )
    with pytest.raises(PolicyError, match="unknown policy keys"):
        load_policy(str(path))


def test_policy_merges_custom_aliases(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "schema": "baysoz-metriccanon/policy-v1",
                "canonical_names": {"legacy.duration": "modern.duration"},
            }
        ),
        encoding="utf-8",
    )
    policy = load_policy(str(path))
    assert policy.canonical_names["legacy.duration"] == "modern.duration"
    assert policy.canonical_names["http.server.duration"] == "http.server.request.duration"
