# Architecture — Baysöz Labs <baysozlabs@proton.me>

`baysoz-metriccanon` is a deterministic, offline verifier for the metric contract at the
instrumentation/export boundary. It never starts a collector, never opens a socket, and never loads
a model. It reads bytes, normalizes them into an immutable fact model, applies pure rules, and emits
content-addressed reports.

## 1. Data flow

```text
input bytes (OTLP JSON | Prometheus text | canonical snapshot)
        |
        v
read_input()               SHA-256 digest, UTF-8 decode, strict format dispatch
        |
        v
normalize.py               parse_*() -> tuple[MetricPoint, ...]
        |                  no inference beyond documented TYPE/policy mappings
        v
rules.py: analyze()        pure functions over immutable dataclasses
        |                  indexed by name, attribute key, and series identity
        v
baseline.py                content-addressed suppression + stale-entry detection
        |
        v
report.py                  human | JSON | SARIF 2.1.0 renderers
        |
        v
cli.py                     exit 0 pass / 1 gate failure / 2 invalid input
```

## 2. Modules

| Module | Responsibility |
| --- | --- |
| `model.py` | Immutable `Attribute`, `Resource`, `Histogram`, `Exemplar`, `MetricPoint`, `Finding`, `Report`, `Rule` |
| `units.py` | UCUM-style catalog, aliases and exact `Decimal` scale factors |
| `policy.py` | Versioned `baysoz-metriccanon/policy-v1`, strict key validation, merged defaults |
| `normalize.py` | Strict parsers for canonical snapshots, OTLP JSON and Prometheus exposition |
| `rules.py` | All semantic invariants; deterministic indexing, sorting and fingerprinting |
| `baseline.py` | Review-based suppression, stale suppression findings, baseline emission |
| `report.py` | Stable human text, machine JSON and SARIF 2.1.0 documents |
| `cli.py` | Argument contract, exit codes, file I/O, error attribution |
| `__main__.py` | `python -m baysoz_metriccanon` entry point |

## 3. Canonical fact model

A `MetricPoint` carries: metric name, instrument kind (`counter`, `gauge`, `histogram`), raw unit,
attribute key/value/type tuples, resource (including `service.name`), source locator, timestamp,
numeric value or histogram structure, exemplars, aggregation temporality, and monotonicity.

The source locator is preserved (`resource[0]/scope[0]/metrics[2]/dataPoints[0]`, `line[17]`,
`points[4]`) so every finding points back to a real location instead of a generic message.

## 4. Invariant catalog

| Rule | Invariant |
| --- | --- |
| `MC001` | One metric name has one instrument kind across all producers |
| `MC002` | One metric name has compatible canonical units after alias/factor normalization |
| `MC003` | Units are in the built-in catalog or explicitly declared in policy |
| `MC004` | Cumulative counters never decrease; delta counters are never negative or non-monotonic |
| `MC005` | Histogram bounds are finite and strictly increasing; bucket counts are non-negative with correct arity and +Inf |
| `MC006` | An attribute key has one value type across points and within a point |
| `MC007` | Attribute keys do not collide by case folding or exact duplication |
| `MC008` | Deprecated semantic-convention metric names are migrated |
| `MC009` | Deprecated semantic-convention attribute keys are migrated |
| `MC010` | Exemplar trace ids are 32 hex characters and span ids are 16 non-zero hex characters |
| `MC011` | Every resource carries `service.name` |
| `MC012` | Identical series are not exported twice at the same timestamp |
| `MC013` | A counter does not mix cumulative and delta temporality |
| `MC014` | Accepted baseline findings still match the analyzed input |
| `MC015` | Histogram bucket total equals the declared count |
| `MC016` | Values and histogram statistics are finite |
| `MC017` | Metric names are lowercase dot- or underscore-separated ASCII identifiers |

Rules are pure: given the same points, policy and input digest they produce the same `Report`.

## 5. Determinism and integrity

- No wall-clock time, UUIDs, environment-dependent ordering, network calls or randomness.
- Findings are sorted by `(rule_id, source, message, fingerprint)`.
- Fingerprints are truncated SHA-256 over rule id, level, message, source and evidence.
- `Report.digest` and `input_digest` are SHA-256 values exposed in JSON/SARIF for CI reproducibility.
- Rendered documents use `sort_keys=True`, fixed separators where applicable, and UTF-8 output.

## 6. Policy and baselines

The built-in policy is intentionally conservative: it contains only widely established semantic
convention migrations (for example `http.server.duration` → `http.server.request.duration`,
`http.method` → `http.request.method`) and common units. Teams extend it with a versioned policy
file rather than relying on guesses.

Baselines store fingerprints, rule ids and human reasons. A suppressed finding stays visible in
SARIF with a `suppressions` justification; an entry that no longer matches produces `MC014` so
stale exceptions cannot accumulate silently. Baselines are audit aids, not cryptographic signatures.

## 7. Failure semantics

| Exit | Meaning |
| ---: | --- |
| 0 | Analysis completed and gate passed |
| 1 | Analysis completed; gate failed at the configured level |
| 2 | Invalid input, policy, baseline, or I/O error; no partial report is produced |

Unsupported formats, unknown Prometheus types, malformed labels and unknown JSON schemas are
rejected with an explicit error. The tool never silently ignores data it cannot parse.

## 8. Complexity and limits

Normalization is linear in input size. Indexing and sorting are `O(P log P)` for `P` points and
`O(F log F)` for `F` findings. Memory is bounded by the parsed snapshot. Very large snapshots should
be split per service or exporter instance in CI.

## 9. Attribution and ownership

Designed, implemented and maintained by Baysöz Labs <baysozlabs@proton.me>.
Repository: https://github.com/yazilimbaysoz-svg/baysoz-metriccanon.
