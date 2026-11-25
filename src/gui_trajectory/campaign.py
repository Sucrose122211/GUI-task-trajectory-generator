"""Portable, seeded work catalogs. No per-worker dataset packaging is required."""

import re
from pathlib import Path

from .data import screen_groups
from .io import digest, file_digest, image_path, load_manifest, read_json, write_json
from .providers import RESOURCE, SCHEMA


def manifest_identity(rows):
    return digest(
        [
            {**row, "image": {k: v for k, v in row["image"].items() if k != "path"}}
            for row in sorted(rows, key=lambda row: row["sample_id"])
        ]
    )


def build_campaign(manifest, name, seed=42, batch_size=30, providers=("codex", "claude")):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
        raise ValueError("Campaign name must use 1-64 letters, digits, underscores or hyphens")
    if type(seed) is not int or type(batch_size) is not int or batch_size < 1:
        raise ValueError("Invalid campaign seed or batch size")
    if (
        not providers
        or len(set(providers)) != len(providers)
        or set(providers) - {"codex", "claude"}
    ):
        raise ValueError("Select unique codex/claude providers")
    rows = load_manifest(manifest)
    if not rows:
        raise ValueError("Cannot distribute an empty manifest")
    for row in rows:
        if file_digest(image_path(manifest, row)) != row["image"]["sha256"]:
            raise ValueError("Campaign image hash mismatch")
    keys = screen_groups(rows)
    groups = {}
    for row in rows:
        groups.setdefault(keys[row["sample_id"]], []).append(row["sample_id"])
    # Hash ordering avoids dependence on input order, machine paths or Python RNG versions.
    ordered = sorted(groups, key=lambda key: (digest([seed, key]), str(key)))
    batches, part = [], []
    for key in ordered:
        group = sorted(groups[key])
        if part and len(part) + len(group) > batch_size:
            batches.append(part)
            part = []
        part.extend(group)
    if part:
        batches.append(part)
    result = {
        "schema_version": 1,
        "partition_version": 1,
        "campaign_id": name,
        "seed": seed,
        "batch_size": batch_size,
        "providers": list(providers),
        "manifest_identity": manifest_identity(rows),
        "prompt_sha256": digest((RESOURCE / "teacher-v1.txt").read_text(encoding="utf-8")),
        "schema_sha256": digest(SCHEMA),
        "batches": [{"batch_id": f"{i:04d}", "sample_ids": part} for i, part in enumerate(batches)],
    }
    result["fingerprint"] = digest(result)
    return result


def load_campaign(path, manifest=None):
    catalog = read_json(path)
    if catalog.get("fingerprint") != digest(
        {key: value for key, value in catalog.items() if key != "fingerprint"}
    ):
        raise ValueError("Campaign catalog fingerprint mismatch")
    if catalog.get("schema_version") != 1 or catalog.get("partition_version") != 1:
        raise ValueError("Unsupported campaign format")
    if catalog["prompt_sha256"] != digest(
        (RESOURCE / "teacher-v1.txt").read_text(encoding="utf-8")
    ) or catalog["schema_sha256"] != digest(SCHEMA):
        raise ValueError("Prompt or response schema changed; use the campaign's code version")
    if manifest is not None:
        rebuilt = build_campaign(
            manifest,
            catalog["campaign_id"],
            catalog["seed"],
            catalog["batch_size"],
            catalog["providers"],
        )
        if rebuilt != catalog:
            raise ValueError("Dataset, partition or prompt differs from this campaign")
    return catalog


def create_campaign(manifest, output, name, seed=42, batch_size=30, providers=("codex", "claude")):
    if Path(output).exists():
        raise ValueError("Campaign already exists; use a new filename")
    catalog = build_campaign(manifest, name, seed, batch_size, providers)
    write_json(output, catalog)
    return {
        "campaign": str(output),
        "batches": len(catalog["batches"]),
        "fingerprint": catalog["fingerprint"],
    }
