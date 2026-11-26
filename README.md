# baysoz-metriccanon

[![CI](https://github.com/yazilimbaysoz-svg/baysoz-metriccanon/actions/workflows/ci.yml/badge.svg)](https://github.com/yazilimbaysoz-svg/baysoz-metriccanon/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Attribution](https://img.shields.io/badge/maintainer-Bays%C3%B6z%20Labs-purple.svg)](mailto:baysozlabs@proton.me)

**Offline OpenTelemetry and Prometheus metric semantic-conformance oracle with deterministic SARIF CI gates.**
Maintained by **Baysöz Labs <baysozlabs@proton.me>** — https://github.com/yazilimbaysoz-svg.

`baysoz-metriccanon` verifies the *metric contract* at the export boundary: one name means one instrument kind, one canonical unit, stable attribute types, valid histograms, monotonic counters, consistent temporality, and clean resource identity. It catches the silent metric loss and distortion documented in live 2026 upstream issues before data reaches a collector or backend.

No services. No agents. No network. No local LLMs. Python 3.13+, standard library only at runtime.

## Install

```bash
git clone https://github.com/yazilimbaysoz-svg/baysoz-metriccanon.git
cd baysoz-metriccanon
uv venv
uv pip install -e .
```

Alternative direct install:

```bash
uv pip install git+https://github.com/yazilimbaysoz-svg/baysoz-metriccanon.git
```

Verify the attributed CLI:

```bash
uv run baysoz-metriccanon --version
```

```text
baysoz-metriccanon 1.0.0 — Baysöz Labs <baysozlabs@proton.me> — offline metric semantic conformance oracle
```

`--help` also carries the same Baysöz Labs attribution and documents every gate option.

## Quick start

```bash
uv run baysoz-metriccanon tests/fixtures/clean.snapshot.json
uv run baysoz-metriccanon tests/fixtures/adversarial.snapshot.json --sarif findings.sarif
uv run baysoz-metriccanon tests/fixtures/adversarial.otlp.json --format json
uv run baysoz-metriccanon tests/fixtures/prometheus.drift.txt --fail-on warning
```

Exit codes: `0` gate passed, `1` gate failed, `2` invalid input/policy/baseline.

## Real CLI output

Clean canonical snapshot:

```text
Baysöz Labs <baysozlabs@proton.me> — baysoz-metriccanon 1.0.0
input: tests/fixtures/clean.snapshot.json (sha256 ac0046e1102bcc46)
policy: built-in
points: 4 | resources: 1 | findings: 0 (errors: 0, warnings: 0, suppressed: 0)
status: no semantic invariant violations detected
gate: PASS (--fail-on error)
signed off by Baysöz Labs <baysozlabs@proton.me>
```

Adversarial snapshot (exit 1; excerpt of a 21-finding run):

```text
points: 18 | resources: 3 | findings: 21 (errors: 21, warnings: 0, suppressed: 0)
MC001 [error] metric http.server.request.duration has conflicting kinds: counter, histogram
MC002 [error] metric http.server.request.duration uses incompatible units: By, s
MC003 [error] unit 'furlong' on metric weird.metric is not recognized
MC004 [error] cumulative counter checkout.orders decreased from 10 to 7
MC004 [error] delta counter batch.jobs has negative value -3
MC005 [error] histogram legacy.latency has invalid structure: missing +Inf bucket
MC006 [error] attribute http.status_code has conflicting value types: int, str
MC007 [error] attribute keys collide after case folding: HTTP.METHOD, http.method
MC008 [error] metric http.server.duration uses a deprecated name; use http.server.request.duration
MC009 [error] attribute http.method is deprecated; use http.request.method
MC010 [error] exemplar on rpc.duration has an invalid trace or span id
MC011 [error] resource for metric uptime has no service.name
MC012 [error] series audit.events has 2 identical points at '2026-11-26T00:00:00Z'
MC013 [error] counter mixed.total mixes cumulative and delta temporality
MC015 [error] histogram rpc.duration bucket total 3 differs from count 4
MC016 [error] metric cache.entries has a non-finite value: nan
MC017 [error] metric name 'HTTP.Requests' violates the lowercase identifier convention
gate: FAIL (--fail-on error)
signed off by Baysöz Labs <baysozlabs@proton.me>
```

Malformed input is rejected instead of silently skipped:

```text
error: unrecognized JSON input: expected schema 'baysoz-metriccanon/v1' or 'resourceMetrics' — Baysöz Labs <baysozlabs@proton.me>
```

## Accepted inputs

| Input | Example | Notes |
| --- | --- | --- |
| Canonical snapshot | `tests/fixtures/clean.snapshot.json` | `schema: baysoz-metriccanon/v1`, documented in `docs/ARCHITECTURE.md` |
| OTLP JSON | `tests/fixtures/adversarial.otlp.json` | `resourceMetrics` → `scopeMetrics` → `sum`/`gauge`/`histogram` |
| Prometheus text | `tests/fixtures/prometheus.txt` | Strict `# TYPE` handling; histogram `le` buckets reconstructed as OTLP-style deltas |

Unsupported Prometheus types, malformed labels, unknown JSON schemas and ambiguous OTLP values are rejected with exit code 2.

## Rule families

| IDs | Family |
| --- | --- |
| `MC001`–`MC002` | Name/kind/unit collision across producers |
| `MC003`, `MC008`–`MC009` | Unit catalog and semantic-convention migrations |
| `MC004`, `MC013` | Counter monotonicity and aggregation temporality |
| `MC005`, `MC015`–`MC016` | Histogram structure, bucket totals and finite values |
| `MC006`–`MC007` | Attribute type and case-folding conflicts |
| `MC010`–`MC012` | Exemplar ids, resource identity and duplicate series |
| `MC014`, `MC017` | Baseline staleness and metric name convention |

The full 17-rule catalog with guidance is embedded in every SARIF run and documented in `docs/ARCHITECTURE.md`.

## Policy and baseline

Extend the conservative built-in policy instead of guessing:

```json
{
  "schema": "baysoz-metriccanon/policy-v1",
  "attribution": "Baysöz Labs <baysozlabs@proton.me>",
  "canonical_names": {"legacy.duration": "modern.duration"},
  "unit_aliases": {"furlong": "1"},
  "prometheus_units": {"http_server_requests_seconds": "s"}
}
```

```bash
uv run baysoz-metriccanon snapshot.json --policy team-policy.json
uv run baysoz-metriccanon snapshot.json --emit-baseline accepted.json --reason "Reviewed by SRE"
uv run baysoz-metriccanon snapshot.json --baseline accepted.json --fail-on error
```

Baselines are content-addressed. A stale entry produces `MC014`; suppressed findings remain visible in SARIF with their justification.

## Architecture

```text
input bytes → read_input (SHA-256) → strict normalization → immutable MetricPoint facts
            → pure analyze() (indexed invariants) → baseline overlay
            → human | JSON | SARIF 2.1.0 → deterministic exit code
```

See `docs/ARCHITECTURE.md` for module boundaries, invariant semantics, failure semantics and complexity,
`docs/MARKET_RESEARCH.md` for live GitHub evidence, `SECURITY.md` for the threat model, and
`docs/TRIBUNAL.md` for the unanimous release verdict — all by Baysöz Labs <baysozlabs@proton.me>.

## Library API

```python
from baysoz_metriccanon import analyze, default_policy, parse_input, read_input, sarif_document

raw, digest = read_input("snapshot.json")
points, services = parse_input(raw, "snapshot.json", default_policy())
report = analyze(points, default_policy(), digest)
print(report.errors, report.warnings, report.digest)
```

## Quality gates

```bash
uv venv && uv pip install -e . && uv pip install pytest && uv run pytest -q
ruff check --select E,F,W,S,B .
semgrep --config p/default --error .
```

Observed at release: 27 tests passed, ruff clean, Semgrep 0 findings, Tribunal unanimous PASS.

## License and contact

MIT — Copyright (c) 2026 Baysöz Labs <baysozlabs@proton.me>.
Security reports and support: baysozlabs@proton.me. No legal entity suffixes are used in this project.
