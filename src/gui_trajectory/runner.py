"""Sequential generation, immutable cohort settings, and resumable jobs."""

import fcntl
import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .data import relocate
from .io import digest, file_digest, image_path, load_manifest, read_json, write_json, write_jsonl
from .providers import RESOURCE, SCHEMA, ProviderError, doctor, invoke
from .validation import validate_output

CODEX_DEFAULT_MODEL = "gpt-6.2-sol"
CODEX_DEFAULT_REASONING_EFFORT = "medium"


def generate(
    manifest,
    provider,
    model,
    output,
    *,
    limit=None,
    timeout=300,
    retries=1,
    dry_run=False,
    binary=None,
):
    if model and model.startswith("-"):
        raise ValueError("Invalid model name")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    if timeout <= 0 or not 0 <= retries <= 5:
        raise ValueError("timeout must be positive; retries must be between 0 and 5")
    output = Path(output).resolve()
    config_path = output / "run.json"
    reasoning_effort = None
    if provider == "codex" and not model:
        # An existing CLI-default run must keep its original settings on resume.
        if not config_path.exists() or read_json(config_path)["config"]["model"] != "cli_default":
            model = CODEX_DEFAULT_MODEL
            reasoning_effort = CODEX_DEFAULT_REASONING_EFFORT
    rows = load_manifest(manifest)
    template = (RESOURCE / "teacher-v1.txt").read_text(encoding="utf-8")
    config = {
        "pipeline_version": __version__,
        "provider": provider,
        "model": model or "cli_default",
        "prompt_sha256": digest(template),
        "schema_sha256": digest(SCHEMA),
        "point_tolerance": 0.002,
    }
    if reasoning_effort is not None:
        config["reasoning_effort"] = reasoning_effort
    for row in rows:
        if file_digest(image_path(manifest, row)) != row["image"]["sha256"]:
            raise ValueError(f"Image hash mismatch: {row['sample_id']}")
    manifest_identity = digest(
        [{**row, "image": {k: v for k, v in row["image"].items() if k != "path"}} for row in rows]
    )
    if dry_run:
        return {
            "dry_run": True,
            "provider": provider,
            "model": model,
            "samples": min(len(rows), limit or len(rows)),
            "config": config,
            "manifest_identity": manifest_identity,
        }
    readiness = doctor(provider, binary)
    if not readiness["ready"]:
        raise ProviderError("auth", readiness["reason"])
    config["cli_version"] = readiness["version"]
    cohort = {"config": config, "manifest_identity": manifest_identity}
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another generator is using this run directory") from exc
        if config_path.exists() and read_json(config_path) != cohort:
            raise ValueError("Run settings or manifest changed; use a new output directory")
        if not config_path.exists():
            write_jsonl(
                output / "manifest.jsonl", relocate(rows, manifest, output / "manifest.jsonl")
            )
            write_json(config_path, cohort)
        summary = {"generated": 0, "skipped": 0, "failed": 0, "halted": None}
        for row in rows:
            job_id = digest([row["sample_id"], config, 0])[:32]
            job_dir = output / "jobs" / job_id
            result_path = job_dir / "result.json"
            if result_path.exists() and read_json(result_path)["state"] == "completed":
                summary["skipped"] += 1
                continue
            if limit is not None and summary["generated"] + summary["failed"] >= limit:
                break
            job_dir.mkdir(parents=True, exist_ok=True)
            existing = list(job_dir.glob("attempt-*.json"))
            start_attempt = max((int(p.stem.split("-")[1]) for p in existing), default=0)
            for retry in range(retries + 1):
                started = time.monotonic()
                result = {
                    "schema_version": 1,
                    "job_id": job_id,
                    "sample_id": row["sample_id"],
                    "role": row["role"],
                    "config": config,
                    "attempt": start_attempt + retry + 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "state": "failed",
                }
                try:
                    with tempfile.TemporaryDirectory(prefix="gui-teacher-") as directory:
                        work = Path(directory)
                        source_image = image_path(manifest, row)
                        suffix = source_image.suffix.lower()
                        if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                            raise ValueError("Unsupported teacher image format")
                        shutil.copyfile(source_image, work / f"screenshot{suffix}")
                        write_json(work / "schema.json", SCHEMA)
                        prompt = template.format(
                            instruction=row["instruction"],
                            answer=json.dumps(
                                {"point": row["answer"]["point"], "bbox": row["answer"]["bbox"]}
                            ),
                        )
                        payload, usage, audit = invoke(
                            provider,
                            model,
                            work,
                            prompt,
                            timeout=timeout,
                            binary=binary,
                            reasoning_effort=reasoning_effort,
                        )
                    result.update(
                        {
                            "state": "completed",
                            "response": payload,
                            "validation": validate_output(payload, row),
                            "usage": usage,
                            "input_audit": audit,
                        }
                    )
                except ProviderError as exc:
                    result["error"] = {"kind": exc.kind, "message": str(exc)}
                result["duration_seconds"] = round(time.monotonic() - started, 3)
                write_json(job_dir / f"attempt-{result['attempt']:04d}.json", result)
                write_json(result_path, result)
                if result["state"] == "completed":
                    summary["generated"] += 1
                    break
                kind = result["error"]["kind"]
                if kind in ("limit", "auth", "setup"):
                    summary["failed"] += 1
                    summary["halted"] = kind
                    write_json(output / "summary.json", summary)
                    return summary
                if kind not in ("execution", "timeout") or retry == retries:
                    summary["failed"] += 1
                    break
                time.sleep(min(2**retry, 5))
        write_json(output / "summary.json", summary)
        return summary
