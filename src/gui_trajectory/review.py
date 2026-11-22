"""Local review sheets and deliberate, reviewed training exports."""

import base64
import csv
import html
import io
import json
import mimetypes
from collections import Counter
from pathlib import Path

from .io import atomic_text, image_path, load_manifest, read_json, write_jsonl

SCORES = ("evidence", "target_match", "usefulness", "consistency")


def results(run):
    return [read_json(p) for p in sorted(Path(run).glob("jobs/*/result.json"))]


def review(run, output):
    run, output = Path(run), Path(output)
    rows = {r["sample_id"]: r for r in load_manifest(run / "manifest.jsonl")}
    output.mkdir(parents=True, exist_ok=True)
    sheet_path = output / "scores.csv"
    existing = {}
    if sheet_path.exists():
        with sheet_path.open(encoding="utf-8", newline="") as stream:
            existing = {r["job_id"]: r for r in csv.DictReader(stream)}
    sections, sheet = [], io.StringIO()
    writer = csv.writer(sheet)
    writer.writerow(["job_id", *SCORES, "decision", "reviewer", "notes"])
    for result in results(run):
        row = rows[result["sample_id"]]
        image = image_path(run / "manifest.jsonl", row)
        mime = mimetypes.guess_type(image.name)[0] or "image/png"
        encoded = base64.b64encode(image.read_bytes()).decode()
        esc = html.escape
        width, height = row["image"]["width"], row["image"]["height"]
        overlay = ""
        box = row["answer"]["bbox"]
        if box:
            x1, y1, x2, y2 = box
            overlay = (
                f'<rect x="{x1 * width}" y="{y1 * height}" '
                f'width="{(x2 - x1) * width}" height="{(y2 - y1) * height}" '
                'fill="none" stroke="#e11d48" stroke-width="2" '
                'vector-effect="non-scaling-stroke"/>'
            )
        sections.append(
            f"<section><h2>{esc(result['job_id'])}</h2>"
            f"<p>{esc(row['instruction'])}</p>"
            f'<svg role="img" aria-label="Original screenshot with reference target in red" '
            f'viewBox="0 0 {width} {height}">'
            f'<image width="{width}" height="{height}" href="data:{mime};base64,{encoded}"/>'
            f"{overlay}</svg>"
            f"<p>Reference answer: {esc(json.dumps(row['answer']))}</p>"
            f"<pre>{esc(json.dumps(result.get('response', result.get('error')), indent=2))}</pre>"
            f"<p>Validation: {esc(json.dumps(result.get('validation', {})))}</p></section>"
        )
        prior = existing.pop(result["job_id"], {})
        writer.writerow(
            [
                result["job_id"],
                *(prior.get(key, "") for key in SCORES),
                prior.get("decision", ""),
                prior.get("reviewer", ""),
                prior.get("notes", ""),
            ]
        )
    for prior in existing.values():
        writer.writerow(
            [
                prior.get(key, "")
                for key in (
                    "job_id",
                    *SCORES,
                    "decision",
                    "reviewer",
                    "notes",
                )
            ]
        )
    atomic_text(
        output / "review.html",
        "<!doctype html><meta charset='utf-8'>"
        "<title>GUI trajectory review</title>"
        "<style>body{font:16px sans-serif;max-width:1200px;margin:2em auto}"
        "svg{width:100%;max-height:800px}pre{white-space:pre-wrap}"
        "section{border-bottom:2px solid #bbb;padding:2em 0}</style>" + "".join(sections),
    )
    # Preserve decisions while appending newly generated jobs to the same sheet.
    atomic_text(sheet_path, sheet.getvalue())
    return {"results": len(sections), "report": str(output / "review.html")}


def export(run, scores, output, allow_pilot=False):
    run, output = Path(run), Path(output)
    samples = {r["sample_id"]: r for r in load_manifest(run / "manifest.jsonl")}
    with Path(scores).open(encoding="utf-8", newline="") as stream:
        decisions = list(csv.DictReader(stream))
    ids = [d["job_id"] for d in decisions]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate job_id in human review sheet")
    decision_map = {d["job_id"]: d for d in decisions}
    all_results = results(run)
    unknown = set(decision_map) - {r["job_id"] for r in all_results}
    if unknown:
        raise ValueError("Review sheet contains unknown job IDs")
    records, excluded = [], []
    for result in all_results:
        decision = decision_map.get(result["job_id"], {})
        sample = samples[result["sample_id"]]
        try:
            values = [int(decision.get(key, "")) for key in SCORES]
            quality = all(1 <= score <= 2 for score in values) and sum(values) >= 6
        except ValueError:
            quality = False
        accepted = (
            decision.get("decision") == "accept"
            and bool(decision.get("reviewer", "").strip())
            and quality
            and result["state"] == "completed"
            and result["validation"]["valid"]
            and result["response"]["status"] == "ok"
        )
        if not accepted:
            excluded.append({"job_id": result["job_id"], "reason": "Not human-approved and valid"})
            continue
        if sample["role"] != "train" and not allow_pilot:
            raise ValueError("Non-training samples cannot be exported without --allow-pilot")
        if sample["role"] not in ("train", "pilot_dev"):
            raise ValueError("Validation/test samples cannot be exported")
        response = result["response"]
        click = response["final_click"]
        trajectory = "\n".join(response["visual_steps"]) + (
            f"\nclick({click['x']:.8f},{click['y']:.8f})"
        )
        records.append(
            {
                "sample_id": sample["sample_id"],
                "job_id": result["job_id"],
                "role": sample["role"],
                "exclude_from_training": sample["role"] != "train",
                "image": str(image_path(run / "manifest.jsonl", sample)),
                "instruction": sample["instruction"],
                "answer": sample["answer"],
                "trajectory": trajectory,
                "visual_steps": response["visual_steps"],
                "source": sample["source"],
                "teacher_config": result["config"],
            }
        )
    write_jsonl(output, records)
    write_jsonl(output.with_suffix(".excluded.jsonl"), excluded)
    return {"exported": len(records), "excluded": len(excluded)}


def report_summary(run):
    counts = Counter()
    for result in results(run):
        if result["state"] != "completed":
            counts[f"failed/{result['error']['kind']}"] += 1
        elif not result["validation"]["valid"]:
            counts["invalid_output"] += 1
        elif result["response"]["status"] == "needs_review":
            counts["teacher_needs_review"] += 1
        else:
            counts["awaiting_human_review"] += 1
    return dict(counts)
