# Market Research — Baysöz Labs <baysozlabs@proton.me>

Project: `baysoz-metriccanon` — offline OpenTelemetry and Prometheus metric semantic-conformance oracle.
Research date: 2026-11-26. Method: live `gh search repos`, `gh search issues`, and `gh api` sampling of
repository metadata. All conclusions below are tied to observed results, not assumptions.

## 1. Live ecosystem signals

### 1.1 Repository scale (`gh search repos`, sorted by stars)

| Repository | Stars (observed) | Last push (UTC) | Signal |
| --- | ---: | --- | --- |
| netdata/netdata | 81,647 | 2026-11-26 | Full-stack observability remains a top-tier OSS category |
| grafana/grafana | 78,187 | 2026-11-25 | Visualization/query layer is mature and enormous |
| prometheus/prometheus | 67,896 | 2026-11-25 (via `gh api`) | Metrics exposition and TSDB are production-critical |
| langfuse/langfuse | 37,853 | 2026-11-26 | AI/agent observability is a fast-growing 2026 wedge |
| SigNoz/signoz | 32,739 | 2026-11-26 | OpenTelemetry-native platforms are mainstream |
| openobserve/openobserve | 23,189 | 2026-11-26 | Log/metric/trace convergence continues |
| vectordotdev/vector | 22,966 | 2026-11-25 | Observability data pipelines are widely deployed |
| open-telemetry/opentelemetry-collector | 7,808 | 2026-11-25 | Collector is the de facto routing/processing layer |
| open-telemetry/opentelemetry-collector-contrib | 5,065 | 2026-11-25 (`gh api`) | Receiver/exporter diversity creates compatibility drift |
| open-telemetry/opentelemetry-specification | 4,403 | 2026-11-25 (`gh api`) | Semantic contract changes are active in 2026 |
| open-telemetry/opentelemetry-python | 2,723 | 2026-11-25 (`gh api`) | SDK-side instrumentation bugs are still being filed |
| open-telemetry/semantic-conventions | 696 | 2026-11-25 (`gh api`) | Conventions are versioned and still evolving |

Interpretation: the ecosystem is not short of collectors, backends, or dashboards. It is short of
*pre-export contract verification* that catches semantic drift before data reaches those systems.

### 1.2 Open issues and ecosystem pain (`gh search issues`)

| Observed issue (repo, date) | Pain point |
| --- | --- |
| micrometer-metrics/micrometer, 2026-10-28 — “The OpenTelemetry JVM conventions don't use the units defined by the conventions” | Unit metadata disagrees across implementations |
| llm-d/llm-d-router, 2026-11-20 — opt-in OTel GenAI semantic-convention metrics compatibility | New 2026 convention families keep arriving |
| mostlygeek/llama-swap, 2026-11-19 — native OpenTelemetry metrics/traces using GenAI conventions | Producers adopt conventions at different times |
| open-telemetry/community, 2026-07-22 — request to reactivate Messaging Semantic Conventions | Convention coverage is incomplete, so local policy extension is necessary |
| kite-org/kite, 2026-07-14 — support OTel semantic conventions as an alternative query metric implementation | Consumers need canonical names to query mixed producers |
| prometheus/prometheus, 2026-10-31 — add service discovery metadata to a single metric | Resource/series identity is a live design concern |
| fluxcd/flux2, 2026-09-08 — multiple resources sharing one metric family silently lose data | Name collision causes silent data loss |
| percona/mongodb_exporter, 2026-09-03 — collected before with same name and label values | Exact duplicate series corrupt collection |
| cadence-workflow/cadence, 2026-08-26 — silently drops metrics with same name due to inconsistent label sets | Attribute schema drift causes drops |
| HsiChinHuang/order-tracker, 2026-09-30 — collector metric-name collision and duplicated identity labels | Collisions surface only in production collectors |
| datadog-labs/ephyra, 2026-11-25 — feature histograms hang or miscount on large values | Histogram correctness is still a 2026 failure mode |
| theagentrouter/agent-router, 2026-11-25 — extend TTFT/duration histogram buckets past 60s/82s | Bucket boundaries drift as services evolve |
| llm-d/llm-d, 2026-11-23 — tracking issue for 1.1 “Deepening Day 2” | Observability is now part of production AI rollout checklists |

The recurring pattern: **silent loss or silent distortion** at the metric contract boundary —
same name with a different kind, incompatible units, drifting attribute types, malformed histograms,
mixed temporality. These failures are cheap to detect offline and expensive to debug in a backend.

Note: follow-up repository-scoped searches encountered GitHub secondary rate limiting after the
queries above; the evidence table only lists results that were actually returned.

## 2. Why this is not a toy or a duplicate

The pre-existing Baysöz Labs portfolio already contains strong tools for adjacent layers:

| Existing project | Layer it owns | Why it is not this project |
| --- | --- | --- |
| `baysoz-tracecontinuity` | W3C trace propagation continuity | No metric name/unit/histogram contract analysis |
| `baysoz-queryoracle` | PromQL conformance and backend portability | Queries, not emitted metric facts |
| `baysoz-alertpath-oracle` | Alertmanager routing/inhibition | Alert paths, not metric schemas |
| `baysoz-burnlattice` | SLO burn-rate policy | Error budgets, not export-boundary drift |
| `baysoz-cardinalis` | Cardinality risk estimation | Label explosion risk, not type/unit/name collisions |
| `baysoz-otelgate` | Collector configuration linting | Pipeline config, not data-plane metric facts |
| `baysoz-profilediff` | pprof differential regression | CPU profiles, not metric contracts |
| `baysoz-corelattice` | eBPF CO-RE/BTF conformance | Kernel type drift, not telemetry semantics |
| `baysoz-logmask`, `envlens`, `envpair` | Log/config hygiene | Different signal and threat model |

`baysoz-metriccanon` fills the missing seam: it consumes the **facts a service emits** (OTLP JSON,
Prometheus exposition, or canonical snapshots) and verifies the metric contract itself. It is a deep
library/CLI, not a dashboard, not a collector, not an agent, and not a service.

## 3. Product decision

- **Language/runtime:** Python 3.13+ with `uv`. Standard library only at runtime; zero heavy
  services, zero local LLMs, zero network calls.
- **Input realism:** OTLP/JSON `resourceMetrics`, Prometheus text exposition (`# TYPE`, histograms
  with `le` labels), and a documented canonical snapshot format for fixtures and CI.
- **Depth:** 17 deterministic invariant rules (16 active finding rules plus baseline staleness),
  UCUM-style alias/factor normalization, semantic-convention migration hints, content-addressed
  fingerprints, auditable baselines, SARIF 2.1.0 CI output.
- **Enterprise fit:** policy files for local convention extensions, `--fail-on error|warning|none`,
  stable exit codes (0 clean / 1 gate failure / 2 invalid input), no timestamps in output.
- **Repository owner:** Baysöz Labs <baysozlabs@proton.me>, https://github.com/yazilimbaysoz-svg.

## 4. Success criteria

1. Every active rule is exercised by a committed adversarial fixture.
2. Repeated runs produce byte-identical human, JSON, and SARIF output.
3. Real upstream-format inputs (OTLP JSON, Prometheus text) are parsed strictly, with explicit
   rejection instead of silent skipping.
4. Quality gates (`pytest`, `ruff E/F/W/S/B`, `semgrep p/default`) report zero findings.
5. A Supreme Grand Jury Tribunal executes the built CLI live on adversarial inputs and returns a
   unanimous PASS before publication.

— Baysöz Labs <baysozlabs@proton.me>
