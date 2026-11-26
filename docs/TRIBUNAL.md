# Supreme Grand Jury Tribunal — Baysöz Labs <baysozlabs@proton.me>

Session: 2026-11-26, after `uv run pytest -q` (27 passed), `ruff check --select E,F,W,S,B .`
(All checks passed), and `semgrep --config p/default --error .` (0 findings).

The Tribunal executed the installed CLI (`baysoz-metriccanon 1.0.0`) and the public library against
real fixture inputs. Verdicts are based on observed output, not assertions of intent.

## Evidence matrix

| Juror | Live evidence | Verdict |
| --- | --- | --- |
| Structural Juror | All required public files exist and contain `Baysöz Labs <baysozlabs@proton.me>` | PASS |
| Semantic Juror | 21 evidence-backed findings spanning all 16 active rules plus 17 SARIF rule descriptors | PASS |
| Determinism Juror | Repeated `--format json` and SARIF runs are byte-identical; no clock/random input | PASS |
| Adversarial Execution Juror | Clean exit 0/0 findings; canonical adversarial exit 1/21 findings; OTLP exit 1/`MC004`; Prometheus exit 1/`MC005`,`MC015`; malformed JSON exit 2 | PASS |
| No-Stub Juror | No `TODO`, `FIXME`, `placeholder`, `stub`, `eval(` or `exec(` in production source; every finding has a rule, source, message and 32-hex fingerprint | PASS |
| Supply-Chain Juror | Python >=3.13, MIT attribution, pinned action SHAs, and all three gates present in CI | PASS |

## Live CLI excerpts

Version:

```text
baysoz-metriccanon 1.0.0 — Baysöz Labs <baysozlabs@proton.me> — offline metric semantic conformance oracle
```

Clean fixture (exit 0):

```text
Baysöz Labs <baysozlabs@proton.me> — baysoz-metriccanon 1.0.0
input: tests/fixtures/clean.snapshot.json (sha256 ac0046e1102bcc46)
policy: built-in
points: 4 | resources: 1 | findings: 0 (errors: 0, warnings: 0, suppressed: 0)
status: no semantic invariant violations detected
gate: PASS (--fail-on error)
signed off by Baysöz Labs <baysozlabs@proton.me>
```

Adversarial fixture (exit 1, first 16 findings shown):

```text
points: 18 | resources: 3 | findings: 21 (errors: 21, warnings: 0, suppressed: 0)
MC001 [error] metric http.server.request.duration has conflicting kinds: counter, histogram
MC002 [error] metric http.server.request.duration uses incompatible units: By, s
MC003 [error] unit 'furlong' on metric weird.metric is not recognized
MC004 [error] cumulative counter checkout.orders decreased from 10 to 7
MC004 [error] delta counter batch.jobs has negative value -3
MC005 [error] histogram legacy.latency has invalid structure: missing +Inf bucket
MC005 [error] histogram rpc.duration has invalid structure: bounds are not strictly increasing; invalid bucket counts
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
```

Malformed input (exit 2):

```text
error: unrecognized JSON input: expected schema 'baysoz-metriccanon/v1' or 'resourceMetrics' — Baysöz Labs <baysozlabs@proton.me>
```

SARIF artifact: version `2.1.0`, 17 rule descriptors, 21 results, invocation exit code 1,
`attribution: Baysöz Labs <baysozlabs@proton.me>`.

## Hallucination and stub check

Every message names a concrete metric, attribute, source locator or value that exists in the input.
Examples verified live: `10 → 7` counter regression, `deadbeef` invalid trace id, `furlong` unknown
unit, `HTTP.METHOD` case collision, and `bucket total 3 differs from count 4`. No generic,
template-only or placeholder finding was observed. The `no_stubs_juror` test scans production source
for stub markers and dynamic execution primitives.

## Verdict

**UNANIMOUS PASS.** Release authorized by Baysöz Labs <baysozlabs@proton.me>.
