"""Deterministic screen-group sharding and collision-aware run merging."""

import re
from pathlib import Path

from .data import relocate, screen_groups
from .io import digest, file_digest, image_path, load_manifest, read_json, write_json, write_jsonl
from .review import results


def shard(manifest, output, count):
    if count < 1:
        raise ValueError("Shard count must be positive")
    rows = load_manifest(manifest)
    groups = {}
    keys = screen_groups(rows)
    for row in rows:
        groups.setdefault(keys[row["sample_id"]], []).append(row)
    parts = [[] for _ in range(count)]
    for key in sorted(groups, key=lambda k: (-len(groups[k]), str(k))):
        target = min(range(count), key=lambda i: (len(parts[i]), i))
        parts[target].extend(groups[key])
    for index, part in enumerate(parts):
        destination = Path(output) / f"shard-{index:03d}.jsonl"
        write_jsonl(destination, relocate(part, manifest, destination))
    return {"shards": count, "sizes": [len(part) for part in parts]}


def merge(runs, output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Merge output must be an empty directory")
    samples, jobs, settings = {}, {}, []
    for run in map(Path, runs):
        manifest = run / "manifest.jsonl"
        settings.append(read_json(run / "run.json"))
        for sample in relocate(load_manifest(manifest), manifest, output / "manifest.jsonl"):
            key = sample["sample_id"]
            if (
                file_digest(image_path(output / "manifest.jsonl", sample))
                != sample["image"]["sha256"]
            ):
                raise ValueError(f"Image hash mismatch: {key}")
            if key in samples:
                # Independent submissions carry separate copies of the same original image.
                def identity(row):
                    return {**row, "image": {k: v for k, v in row["image"].items() if k != "path"}}

                if identity(samples[key]) != identity(sample):
                    raise ValueError(f"Conflicting sample: {key}")
            else:
                samples[key] = sample
        for result in results(run):
            key = result["job_id"]
            if not re.fullmatch(r"[0-9a-f]{32}", key):
                raise ValueError("Invalid job ID")
            if key in jobs and digest(jobs[key]) != digest(result):
                raise ValueError(f"Conflicting result for job {key}")
            if result["sample_id"] not in samples:
                raise ValueError("Result refers to a missing sample")
            jobs[key] = result
    write_jsonl(output / "manifest.jsonl", sorted(samples.values(), key=lambda r: r["sample_id"]))
    write_json(output / "run.json", {"merged_runs": settings})
    for key, result in jobs.items():
        write_json(output / "jobs" / key / "result.json", result)
    return {"samples": len(samples), "jobs": len(jobs)}
