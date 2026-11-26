# Security Policy — Baysöz Labs <baysozlabs@proton.me>

Project: `baysoz-metriccanon`. Maintainer: Baysöz Labs <baysozlabs@proton.me>.
Repository: https://github.com/yazilimbaysoz-svg/baysoz-metriccanon.

## 1. Trust model

The tool runs in a CI runner or developer shell on untrusted telemetry snapshots, policy files and
baselines. Input bytes are untrusted; the local filesystem path is supplied by the operator; output
paths are operator-controlled. The tool has no network privileges, no service dependencies and no
model inference.

## 2. Threats and mitigations

| Threat | Mitigation |
| --- | --- |
| Malicious JSON/protobuf-shaped input causes crashes | Strict dispatch, typed parsing, bounded helpers, all parse failures become exit code 2 with attribution |
| Prometheus label injection or parser confusion | Manual quoted-label scanner with explicit escape table; unsupported escapes are rejected |
| Silent data dropping | Unknown schemas, types, suffixes and value encodings are rejected, never ignored |
| NaN/Infinity poisoning aggregations | `MC016` flags non-finite values and histogram statistics |
| Cross-producer contract drift | `MC001`, `MC002`, `MC006`, `MC007`, `MC013` compare indexed facts globally |
| Duplicate or colliding series | `MC012`, `MC007` use canonicalized identity keys and case folding |
| Stale CI exceptions | Content-addressed baselines; unmatched entries generate `MC014` |
| Dynamic code execution | No `eval`, `exec`, `pickle`, `subprocess`, `shell=True` or plugin loading in production code |
| Weak hashing | SHA-256 only for digests and fingerprints; no cryptographic signing claim |
| Dependency supply chain | Standard library at runtime; build uses Hatchling; CI pins Python 3.13 and runs static/security gates |
| Secret leakage | Findings include only metric/attribute names, values and source locators; no environment dumps |

## 3. Baseline caveat

Baselines are review records keyed by content fingerprint, not signatures. An attacker who can edit
the baseline file can suppress findings. Protect baseline files with normal code-review and branch
protection; the `reason` field and input digest make unreviewed edits visible in diffs.

## 4. Safe usage

```bash
uv run baysoz-metriccanon snapshot.json --fail-on error --sarif results.sarif
```

Treat SARIF and JSON output as build artifacts. Do not publish raw telemetry snapshots containing
secrets; use `baysoz-logmask` or equivalent before exporting logs that may contain PII.

## 5. Static and security gates

Every change must pass:

```bash
uv venv && uv pip install -e . && uv pip install pytest && uv run pytest -q
ruff check --select E,F,W,S,B .
semgrep --config p/default --error .
```

## 6. Reporting vulnerabilities

Report security issues privately to Baysöz Labs <baysozlabs@proton.me>. Include a minimal reproducer,
the affected version from `baysoz-metriccanon --version`, and the observed exit code. Please do not
open public issues for undisclosed vulnerabilities.

— Baysöz Labs <baysozlabs@proton.me>
