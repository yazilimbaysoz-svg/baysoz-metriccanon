# Plan — Baysöz Labs <baysozlabs@proton.me>

## Phase 1 — Market validation (complete)

- Inspected `existing-repos.json` (39 repositories) and mapped adjacent observability tooling.
- Mined live GitHub trends and issues with `gh search repos`, `gh search issues` and `gh api`.
- Selected the metric-contract seam: silent name/kind/unit/attribute/histogram drift at export time.
- Evidence recorded in `docs/MARKET_RESEARCH.md`.

## Phase 2 — Deep implementation (complete)

- Python 3.13+ package under `src/baysoz_metriccanon/` with zero runtime third-party dependencies.
- Strict canonical, OTLP JSON and Prometheus text normalization.
- Immutable fact model, exact-decimal unit canonicalization, versioned policy extension.
- 17-rule deterministic invariant engine with stable fingerprints and content digests.
- Auditable baselines, stale-suppression detection, human/JSON/SARIF 2.1.0 renderers.
- CLI with `--version`, `--help`, `--format`, `--sarif`, `--policy`, `--baseline`,
  `--emit-baseline`, `--fail-on`, and deterministic exit codes.

## Phase 3 — Enterprise documentation and CI (complete)

- `README.md`, `docs/MARKET_RESEARCH.md`, `docs/ARCHITECTURE.md`, `PLAN.md`, `SECURITY.md`,
  `CHANGELOG.md`, MIT `LICENSE`, `pyproject.toml`, `.github/workflows/ci.yml`, `.gitignore`.
- Every public file carries explicit Baysöz Labs attribution and email.
- CI enforces `pytest`, `ruff --select E,F,W,S,B`, `semgrep --config p/default --error`,
  attribution checks and live CLI smoke tests.

## Phase 4 — Zero-defect quality gates (complete)

- `uv venv && uv pip install -e . && uv pip install pytest && uv run pytest -q`
- `ruff check --select E,F,W,S,B .`
- `semgrep --config p/default --error .`
- Iteration continues in CI on every push and pull request; no finding is waived.

## Phase 5 — Supreme Grand Jury Tribunal (complete)

Jurors execute the installed CLI and library against clean, adversarial, OTLP, Prometheus and
malformed inputs. They verify evidence-backed findings, stable fingerprints, byte-identical repeat
runs, absence of stubs/dynamic execution, and enforcement of the dependency/CI contract. A release
requires unanimous PASS, recorded in `docs/TRIBUNAL.md`.

## Phase 6 — Publication (complete)

- Public repository under `yazilimbaysoz-svg`, with crisp description and topical metadata.
- Factory result written only to the designated showcase JSON file.

## Non-goals

- Collector, agent, server, database, dashboard or web UI.
- Network calls, remote schema fetching, local LLMs, or heavyweight services.
- Guessing unit or name mappings that are not in the built-in policy or user policy.

— Baysöz Labs <baysozlabs@proton.me>
