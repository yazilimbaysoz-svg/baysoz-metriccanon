"""Baysöz Labs <baysozlabs@proton.me> — offline metric conformance CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .baseline import BaselineError, apply_baseline, load_baseline, write_baseline
from .model import Report
from .normalize import InputError, parse_input, read_input
from .policy import PolicyError, load_policy
from .report import ATTRIBUTION, json_document, render_text, sarif_document
from .rules import analyze
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="baysoz-metriccanon",
        description=(
            f"{ATTRIBUTION} — Offline OpenTelemetry and Prometheus metric "
            "semantic-conformance oracle with deterministic SARIF gates."
        ),
        epilog=(f"All analysis is local, deterministic and network-free. {ATTRIBUTION}."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=(
            f"baysoz-metriccanon {__version__} — {ATTRIBUTION} — "
            "offline metric semantic conformance oracle"
        ),
    )
    parser.add_argument(
        "input", nargs="?", help="OTLP JSON, Prometheus text, or snapshot JSON file"
    )
    parser.add_argument("--policy", help="versioned policy JSON (baysoz-metriccanon/policy-v1)")
    parser.add_argument("--baseline", help="accepted-finding baseline JSON")
    parser.add_argument("--emit-baseline", help="write a reviewed baseline from current findings")
    parser.add_argument(
        "--reason",
        default="Reviewed by operator",
        help="justification stored in an emitted baseline",
    )
    parser.add_argument(
        "--format",
        choices=("human", "json", "sarif"),
        default="human",
        help="stdout report format (default: human)",
    )
    parser.add_argument("--sarif", help="also write the SARIF 2.1.0 document to this path")
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "none"),
        default="error",
        help="finding level that fails the gate (default: error)",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the stdout report")
    return parser


def _write(path: str, payload: str) -> None:
    Path(path).write_text(payload, encoding="utf-8")


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.input:
        parser.error("an input file is required (or use --version/--help)")
    policy = load_policy(args.policy)
    raw, digest = read_input(args.input)
    points, _resources = parse_input(raw, args.input, policy)
    report: Report = analyze(points, policy, digest)
    baseline = load_baseline(args.baseline)
    if args.emit_baseline:
        write_baseline(report, args.emit_baseline, args.reason, args.input, policy.digest)
        if not args.quiet:
            print(f"baseline written: {args.emit_baseline} — {ATTRIBUTION}")
        return 0
    report = apply_baseline(report, baseline, f"baseline:{args.baseline}")
    if args.sarif:
        document = sarif_document(report, policy, args.input, args.fail_on)
        _write(
            args.sarif, json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    if not args.quiet:
        if args.format == "json":
            document = json_document(report, policy, args.input, args.fail_on)
            print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
        elif args.format == "sarif":
            document = sarif_document(report, policy, args.input, args.fail_on)
            print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(render_text(report, args.input, args.fail_on, policy.source))
    return 1 if report.gate_failed(args.fail_on) else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args, parser)
    except (InputError, PolicyError, BaselineError, OSError, ValueError) as exc:
        print(f"error: {exc} — {ATTRIBUTION}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
