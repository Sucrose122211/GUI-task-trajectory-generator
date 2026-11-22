"""Public command-line entry point. Host generation uses only the standard library."""

import argparse
import json
import sys
from pathlib import Path

from .bundles import bundle_data, bundle_run
from .data import prepare, relocate, select_pilot
from .fetch import fetch_screenspot
from .io import load_manifest, read_json, write_json, write_jsonl
from .operations import merge, shard
from .providers import ProviderError, doctor
from .review import export, report_summary, review
from .runner import generate


def parser():
    root = argparse.ArgumentParser(prog="gui-trajectory")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("help")
    fetch = sub.add_parser("fetch-screenspot", help="Download the official dataset (about 1.3 GB)")
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--revision", default="main")
    prep = sub.add_parser("prepare", help="Convert source annotations into a common manifest")
    prep.add_argument("--adapter", choices=("screenspot_v2", "os_atlas", "mapped"), required=True)
    prep.add_argument("--annotations", type=Path, required=True)
    prep.add_argument("--image-root", type=Path, required=True)
    prep.add_argument("--dataset", required=True)
    revision = prep.add_mutually_exclusive_group(required=True)
    revision.add_argument("--revision")
    revision.add_argument("--source-info", type=Path)
    prep.add_argument("--role", choices=("pilot_dev", "train", "validation", "test"), required=True)
    prep.add_argument("--mapping", type=Path)
    prep.add_argument("--output", type=Path, required=True)
    pilot = sub.add_parser("pilot", help="Select deterministic, balanced distinct screens")
    pilot.add_argument("--manifest", type=Path, required=True)
    pilot.add_argument("--count", type=int, default=30)
    pilot.add_argument("--seed", type=int, default=42)
    pilot.add_argument("--output", type=Path, required=True)
    doc = sub.add_parser("doctor", help="Check subscription login without inference")
    doc.add_argument("--provider", choices=("codex", "claude", "both"), default="both")
    gen = sub.add_parser("generate", help="Run a subscription teacher on the host")
    gen.add_argument("--manifest", type=Path, required=True)
    gen.add_argument("--provider", choices=("codex", "claude"), required=True)
    gen.add_argument("--model", help="Optional model override; otherwise use CLI default")
    gen.add_argument("--output", type=Path, required=True)
    gen.add_argument("--limit", type=int)
    gen.add_argument("--timeout", type=int, default=300)
    gen.add_argument("--retries", type=int, default=1)
    gen.add_argument("--dry-run", action="store_true")
    rev = sub.add_parser("review", help="Create local HTML review and an editable scores CSV")
    rev.add_argument("--run", type=Path, required=True)
    rev.add_argument("--output", type=Path, required=True)
    exp = sub.add_parser("export", help="Export only manually accepted, valid demonstrations")
    exp.add_argument("--run", type=Path, required=True)
    exp.add_argument("--scores", type=Path, required=True)
    exp.add_argument("--output", type=Path, required=True)
    exp.add_argument("--allow-pilot", action="store_true")
    sha = sub.add_parser("shard", help="Assign whole screen groups to workers")
    sha.add_argument("--manifest", type=Path, required=True)
    sha.add_argument("--count", type=int, required=True)
    sha.add_argument("--output", type=Path, required=True)
    mer = sub.add_parser("merge", help="Merge runs while rejecting conflicting job results")
    mer.add_argument("--runs", type=Path, nargs="+", required=True)
    mer.add_argument("--output", type=Path, required=True)
    summary = sub.add_parser("summary")
    summary.add_argument("--run", type=Path, required=True)
    data_bundle = sub.add_parser("bundle-data", help="Pack a manifest with its original images")
    data_bundle.add_argument("--manifest", type=Path, required=True)
    data_bundle.add_argument("--output", type=Path, required=True)
    run_bundle = sub.add_parser("bundle-run", help="Pack portable results for team submission")
    run_bundle.add_argument("--run", type=Path, required=True)
    run_bundle.add_argument("--output", type=Path, required=True)
    return root


def dispatch(args):
    if args.command == "fetch-screenspot":
        return fetch_screenspot(args.output, args.revision)
    if args.command == "prepare":
        if args.adapter == "mapped" and not args.mapping:
            raise ValueError("mapped adapter requires --mapping")
        revision = args.revision
        if args.source_info:
            source = read_json(args.source_info)
            if source["dataset"] != args.dataset:
                raise ValueError("source-info dataset does not match --dataset")
            revision = source["revision"]
        return prepare(
            args.annotations,
            args.image_root,
            args.output,
            args.adapter,
            args.dataset,
            revision,
            args.role,
            read_json(args.mapping) if args.mapping else None,
        )
    if args.command == "pilot":
        rows, counts = select_pilot(load_manifest(args.manifest), args.count, args.seed)
        if any(row["role"] != "pilot_dev" for row in rows):
            raise ValueError("pilot requires a pilot_dev manifest")
        write_jsonl(args.output, relocate(rows, args.manifest, args.output))
        result = {"count": len(rows), "seed": args.seed, "strata": counts}
        write_json(args.output.with_suffix(".selection.json"), result)
        return result
    if args.command == "doctor":
        providers = ("codex", "claude") if args.provider == "both" else (args.provider,)
        statuses = [doctor(provider) for provider in providers]
        return {"ready": all(s["ready"] for s in statuses), "teachers": statuses}
    if args.command == "generate":
        return generate(
            args.manifest,
            args.provider,
            args.model,
            args.output,
            limit=args.limit,
            timeout=args.timeout,
            retries=args.retries,
            dry_run=args.dry_run,
        )
    if args.command == "review":
        return review(args.run, args.output)
    if args.command == "export":
        return export(args.run, args.scores, args.output, args.allow_pilot)
    if args.command == "shard":
        return shard(args.manifest, args.output, args.count)
    if args.command == "merge":
        return merge(args.runs, args.output)
    if args.command == "summary":
        return report_summary(args.run)
    if args.command == "bundle-data":
        return bundle_data(args.manifest, args.output)
    if args.command == "bundle-run":
        return bundle_run(args.run, args.output)
    return None


def main():
    root = parser()
    args = root.parse_args()
    if args.command == "help":
        root.print_help()
        return
    try:
        result = dispatch(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if isinstance(result, dict) and (
            result.get("halted") or result.get("ready") is False or result.get("failed", 0)
        ):
            sys.exit(2)
    except (ValueError, OSError, ProviderError, KeyError) as exc:
        # CLI errors are generated locally; subprocess stdout/auth payloads are never printed.
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
