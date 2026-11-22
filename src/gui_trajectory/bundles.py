"""Explicit, portable distribution archives without host credentials or logs."""

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

from . import __version__
from .io import file_digest, image_path, load_manifest, read_json
from .review import results

SOURCE_FILES = (
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
    ".github/workflows/check.yml",
    "team",
    "pipeline",
    "QUICKSTART.md",
    "AGENTS.md",
    "Dockerfile",
    "Makefile",
    "pyproject.toml",
    "requirements-dev.txt",
    "docs/pipeline-usage.md",
    "docs/agent-manual.md",
    "docs/dataset-adaptation.md",
    "docs/github-distribution.md",
    "docs/usage-skill.md",
    ".agents/skills/gui-trajectory-usage/SKILL.md",
    ".agents/skills/gui-trajectory-usage/agents/openai.yaml",
    ".agents/skills/gui-trajectory-usage/references/coordinator.md",
    ".agents/skills/gui-trajectory-usage/references/worker.md",
    ".claude/skills/사용법/SKILL.md",
    "configs/mapped-example.json",
    "examples/demo/annotations.json",
    "examples/demo/mapping.json",
    "examples/demo/images/toolbar.png",
)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def archive(output, files, metadata):
    """Only explicitly supplied files enter the archive; never recurse over a workspace."""
    output = Path(output).resolve()
    if output.suffix != ".zip":
        raise ValueError("Bundle output must end in .zip")
    if output.exists():
        raise ValueError("Bundle output already exists; choose a new filename")
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = output.stem
    checksums = []
    for name, source in sorted(files.items()):
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Unsafe bundle member")
        if isinstance(source, Path):
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Expected a regular distribution file: {name}")
            sha = file_digest(source)
        else:
            sha = hashlib.sha256(source).hexdigest()
        checksums.append(f"{sha}  {name}\n")
    files = {**files, "BUNDLE.json": encoded(metadata)}
    checksums.append(f"{hashlib.sha256(files['BUNDLE.json']).hexdigest()}  BUNDLE.json\n")
    files["SHA256SUMS.txt"] = "".join(checksums).encode()
    fd, temporary = tempfile.mkstemp(prefix=".bundle-", suffix=".zip", dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as zipped:
            for name, source in sorted(files.items()):
                member = f"{prefix}/{name}"
                if isinstance(source, Path):
                    zipped.write(source, member)
                else:
                    info = zipfile.ZipInfo(member)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    zipped.writestr(info, source)
        os.chmod(temporary, 0o644)
        # A concurrent writer must not cause an existing deliverable to be replaced.
        os.link(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {**metadata, "archive": str(output), "sha256": file_digest(output)}


def portable_samples(manifest):
    rows, files = [], {}
    for row in load_manifest(manifest):
        source = image_path(manifest, row)
        sha = file_digest(source)
        if sha != row["image"]["sha256"]:
            raise ValueError(f"Image hash mismatch: {row['sample_id']}")
        name = f"images/{sha}{source.suffix.lower()}"
        files[name] = source
        rows.append({**row, "image": {**row["image"], "path": name}})
    if not rows:
        raise ValueError("Cannot bundle an empty manifest")
    files["manifest.jsonl"] = b"".join(
        (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode() for row in rows
    )
    return rows, files


def bundle_data(manifest, output):
    rows, files = portable_samples(manifest)
    files["README.txt"] = (
        b"Unzip this archive under the distribution's data/ directory.\n"
        b"Run ./team init --provider codex --manifest data/<folder>/manifest.jsonl\n"
        b"Or choose --provider claude. Then ./team plan and ./team run --limit 1.\n"
    )
    return archive(output, files, {"kind": "dataset", "version": __version__, "samples": len(rows)})


def bundle_run(run, output):
    run = Path(run)
    rows, files = portable_samples(run / "manifest.jsonl")
    sample_ids = {row["sample_id"] for row in rows}
    settings = run / "run.json"
    read_json(settings)
    files["run.json"] = settings
    collected = results(run)
    if not collected:
        raise ValueError("No generated results to submit")
    for result in collected:
        job = result["job_id"]
        if not re.fullmatch(r"[0-9a-f]{32}", job) or result["sample_id"] not in sample_ids:
            raise ValueError("Invalid job identity in submission")
        files[f"jobs/{job}/result.json"] = encoded(result)
    scores = run / "review/scores.csv"
    if scores.exists():
        files["review/scores.csv"] = scores
    files["README.txt"] = (
        b"This is a portable run with original images and latest results.\n"
        b"Extract all teammate archives under runs/incoming/, then merge into a new directory:\n"
        b"./pipeline merge --runs runs/incoming/<folder-a> runs/incoming/<folder-b> "
        b"--output runs/merged\n"
        b"./pipeline review --run runs/merged --output runs/merged/review\n"
        b"Each review/scores.csv is preserved separately; merge does not combine human scores.\n"
    )
    return archive(
        output,
        files,
        {"kind": "run", "version": __version__, "samples": len(rows), "jobs": len(collected)},
    )


def release(root, output):
    root = Path(root)
    names = list(SOURCE_FILES)
    for folder, pattern in (("src/gui_trajectory", "*.py"), ("tests", "*.py")):
        names.extend(str(p.relative_to(root)) for p in sorted((root / folder).glob(pattern)))
    names.extend(
        str(p.relative_to(root)) for p in sorted((root / "src/gui_trajectory/resources").glob("*"))
    )
    files = {name: root / name for name in names}
    files["README.md"] = root / "QUICKSTART.md"
    return archive(output, files, {"kind": "software", "version": __version__})
