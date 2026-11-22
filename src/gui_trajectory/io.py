"""Portable manifests and atomic, non-shared result files."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def file_digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    records = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                records.append(json.loads(line))
            except ValueError as exc:
                raise ValueError(f"Invalid JSON on line {number} of {path}") from exc
    return records


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, records):
    atomic_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in records),
    )


def image_path(manifest, sample):
    return (Path(manifest).resolve().parent / sample["image"]["path"]).resolve()


def load_manifest(path):
    rows = read_jsonl(path)
    ids = [row["sample_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate sample_id in manifest")
    for row in rows:
        if row.get("schema_version") != 1:
            raise ValueError("Unsupported manifest schema_version")
        if not image_path(path, row).is_file():
            raise ValueError(f"Missing image for {row['sample_id']}")
    return rows
