# Changelog — Baysöz Labs <baysozlabs@proton.me>

All notable changes to `baysoz-metriccanon` are documented here.
Maintainer: Baysöz Labs <baysozlabs@proton.me>.

## 1.0.0 — 2026-11-26

### Added

- Strict offline normalization for canonical snapshots, OTLP JSON `resourceMetrics`, and
  Prometheus text exposition with typed label parsing and histogram bucket reconstruction.
- Immutable metric fact model with resource identity, attributes, exemplars, temporality and
  histogram structure.
- UCUM-style unit canonicalization with exact decimal scale factors and a versioned policy file
  for team-specific aliases, migrations and Prometheus unit mappings.
- 17 deterministic semantic invariants covering kind/unit/attribute collisions, deprecated names,
  counter monotonicity, histogram integrity, exemplar ids, duplicate series, temporality conflicts,
  non-finite values and identifier conventions.
- Content-addressed findings, report digests, reviewed baselines and stale-suppression detection.
- Human, machine JSON and SARIF 2.1.0 reporters with stable ordering and explicit attribution.
- CLI with `--version`, `--help`, `--format`, `--sarif`, `--policy`, `--baseline`,
  `--emit-baseline`, `--fail-on`, and exit codes 0/1/2.
- Python 3.13+ packaging with `uv`, zero runtime third-party dependencies, MIT license, CI quality
  gates and adversarial fixture suite.

### Changed

- Initial public release under `yazilimbaysoz-svg`.

### Fixed

- None; initial release.

— Baysöz Labs <baysozlabs@proton.me>
