"""Source-specific parsing ends at a versioned, normalized sample contract."""

import hashlib
import math
import os
import random
from collections import Counter, defaultdict
from pathlib import Path

from .io import digest, file_digest, read_json, read_jsonl, write_json, write_jsonl

SCREENSPOT_MAPPING = {
    "image": "img_filename",
    "instruction": "instruction",
    "bbox": "bbox",
    "bbox_format": "xywh",
    "units": "pixels",
    "element_type": "data_type",
}
OS_ATLAS_MAPPING = {**SCREENSPOT_MAPPING, "bbox_format": "xyxy", "units": "normalized"}


def field(record, name, default=None):
    if not name:
        return default
    value = record
    for part in name.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def normalized_coordinates(values, units, size):
    if not isinstance(values, (list, tuple)) or len(values) not in (2, 4):
        raise ValueError("Coordinates must contain 2 or 4 numbers")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise ValueError("Coordinates must be numbers")
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Non-finite coordinates")
    factors = {"pixels": size, "normalized": (1, 1), "1000": (1000, 1000)}
    if units not in factors:
        raise ValueError(f"Unknown coordinate units: {units}")
    divisor = factors[units]
    result = [float(v) / divisor[i % 2] for i, v in enumerate(values)]
    if any(v < 0 or v > 1 for v in result):
        raise ValueError("Coordinates outside the original image")
    return result


def normalize_answer(record, mapping, size):
    box = field(record, mapping.get("bbox"))
    point = field(record, mapping.get("point"))
    units = mapping["units"]
    original = {"bbox": box, "point": point, "units": units}
    normalized_box = None
    if box is not None:
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ValueError("bbox must contain four numbers")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in box):
            raise ValueError("bbox must contain numbers")
        if mapping.get("bbox_format") == "xywh":
            x, y, width, height = box
            box = [x, y, x + width, y + height]
        elif mapping.get("bbox_format") != "xyxy":
            raise ValueError("bbox_format must explicitly be xywh or xyxy")
        original["bbox_format"] = mapping["bbox_format"]
        normalized_box = normalized_coordinates(box, units, size)
        x1, y1, x2, y2 = normalized_box
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox has no positive area")
    if point is not None:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("point must contain two numbers")
        normalized_point = normalized_coordinates(point, units, size)
        origin = "source_point"
    elif normalized_box is not None:
        x1, y1, x2, y2 = normalized_box
        normalized_point = [(x1 + x2) / 2, (y1 + y2) / 2]
        origin = "derived_box_center"
    else:
        raise ValueError("No supported point or bbox answer")
    if normalized_box:
        x, y = normalized_point
        x1, y1, x2, y2 = normalized_box
        if not (x1 <= x <= x2 and y1 <= y <= y2):
            raise ValueError("Source point is outside source bbox")
    return {
        "point": normalized_point,
        "bbox": normalized_box,
        "coordinate_system": "normalized_original_xy",
        "answer_origin": origin,
        "original": original,
    }


def source_records(path, mapping):
    records = read_jsonl(path) if path.suffix == ".jsonl" else read_json(path)
    records = (
        field(records, mapping.get("records_path")) if mapping.get("records_path") else records
    )
    if not isinstance(records, list):
        raise ValueError(f"Expected a list of records in {path}")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            yield str(index), {}, "Record is not an object"
            continue
        items_path = mapping.get("items_path")
        items = field(record, items_path) if items_path else [record]
        if not isinstance(items, list):
            yield str(index), {}, "items_path is not a list"
            continue
        for subindex, item in enumerate(items):
            if not isinstance(item, dict):
                yield f"{index}:{subindex}", {}, "Item is not an object"
                continue
            # Child fields override parent fields; dotted paths also remain supported.
            merged = {**record, **item} if items_path else record
            identifier = str(field(merged, mapping.get("id"), f"{index}:{subindex}"))
            yield identifier, merged, None


def prepare(annotations, image_root, output, adapter, dataset, revision, role, mapping=None):
    from PIL import Image, ImageOps

    if not revision.strip():
        raise ValueError("A dataset revision is required")
    if adapter == "screenspot_v2" and role != "pilot_dev":
        raise ValueError("ScreenSpot-v2 is reserved for pilot_dev in this project")
    mapping = mapping or (SCREENSPOT_MAPPING if adapter == "screenspot_v2" else OS_ATLAS_MAPPING)
    root, output = Path(image_root).resolve(), Path(output).resolve()
    paths = (
        sorted(Path(annotations).glob("screenspot_*_v2.json"))
        if Path(annotations).is_dir()
        else [Path(annotations)]
    )
    if not paths:
        raise ValueError("No annotation files found")
    rows, errors, seen = [], [], set()
    image_cache = {}
    for path in paths:
        for identifier, record, initial_error in source_records(path, mapping):
            try:
                if initial_error:
                    raise ValueError(initial_error)
                filename = field(record, mapping.get("image"))
                instruction = field(record, mapping.get("instruction"))
                if not isinstance(filename, str) or not filename:
                    raise ValueError("Missing image filename")
                if not isinstance(instruction, str) or not instruction.strip():
                    raise ValueError("Missing instruction")
                image = (root / filename).resolve()
                if not image.is_relative_to(root):
                    raise ValueError("Image path escapes image_root")
                if image not in image_cache:
                    with Image.open(image) as opened:
                        opened.load()
                        if opened.getexif().get(274, 1) != 1:
                            raise ValueError(
                                "EXIF orientation changes coordinates; normalize upstream"
                            )
                        oriented = ImageOps.exif_transpose(opened)
                        width, height = opened.size
                        pixel_hash = digest(
                            [
                                width,
                                height,
                                hashlib.sha256(oriented.convert("RGB").tobytes()).hexdigest(),
                            ]
                        )
                    image_cache[image] = (width, height, file_digest(image), pixel_hash)
                width, height, sha, pixel_hash = image_cache[image]
                answer = normalize_answer(record, mapping, (width, height))
                source = {
                    "dataset": dataset,
                    "revision": revision,
                    "annotation_file": path.name,
                    "record_id": identifier,
                    "adapter": adapter,
                    "adapter_version": 1,
                }
                sample_id = digest([source, sha, instruction, answer])[:24]
                if sample_id in seen:
                    raise ValueError("Duplicate source record")
                seen.add(sample_id)
                platform = field(record, mapping.get("platform"), mapping.get("platform_value"))
                if adapter == "screenspot_v2":
                    platform = path.stem.removeprefix("screenspot_").removesuffix("_v2")
                kind = str(field(record, mapping.get("element_type"), "unknown")).lower()
                if kind in ("widget", "icon/widget"):
                    kind = "icon"
                rows.append(
                    {
                        "schema_version": 1,
                        "sample_id": sample_id,
                        "source": source,
                        "role": role,
                        "image": {
                            "path": os.path.relpath(image, output.parent),
                            "sha256": sha,
                            "width": width,
                            "height": height,
                        },
                        "instruction": instruction,
                        "answer": answer,
                        "group_id": pixel_hash,
                        "source_group": field(record, mapping.get("group")),
                        "attributes": {"platform": platform or "unknown", "element_type": kind},
                    }
                )
            except (ValueError, OSError, TypeError) as exc:
                errors.append(
                    {"annotation_file": path.name, "record_id": identifier, "error": str(exc)}
                )
    write_jsonl(output, rows)
    summary = {"valid": len(rows), "invalid": len(errors), "errors": errors}
    write_json(output.with_suffix(".prepare.json"), summary)
    return summary


def screen_groups(rows):
    """Unify both pixel duplicates and declared original-screen groups."""
    parents = {}

    def find(key):
        parents.setdefault(key, key)
        if parents[key] != key:
            parents[key] = find(parents[key])
        return parents[key]

    for row in rows:
        pixel = "pixels:" + row["group_id"]
        find(pixel)
        if row.get("source_group") is not None:
            source = "source:" + digest([row["source"]["dataset"], row["source_group"]])
            a, b = sorted((find(pixel), find(source)))
            parents[b] = a
    return {row["sample_id"]: find("pixels:" + row["group_id"]) for row in rows}


def select_pilot(rows, count=30, seed=42):
    if count <= 0:
        raise ValueError("Pilot size must be positive")
    buckets = defaultdict(list)
    for row in sorted(rows, key=lambda r: r["sample_id"]):
        a = row["attributes"]
        buckets[(a["platform"], a["element_type"])].append(row)
    rng = random.Random(seed)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    selected, groups = [], set()
    group_keys = screen_groups(rows)
    while len(selected) < count:
        advanced = False
        for key in sorted(buckets):
            while buckets[key]:
                row = buckets[key].pop()
                group = group_keys[row["sample_id"]]
                if group not in groups:
                    groups.add(group)
                    selected.append(row)
                    advanced = True
                    break
            if len(selected) == count:
                break
        if not advanced:
            break
    if len(selected) != count:
        raise ValueError(f"Requested {count} samples, found {len(selected)} distinct screen groups")
    counts = Counter(
        f"{r['attributes']['platform']}/{r['attributes']['element_type']}" for r in selected
    )
    return selected, dict(sorted(counts.items()))


def relocate(rows, source_manifest, destination):
    from .io import image_path

    return [
        {
            **r,
            "image": {
                **r["image"],
                "path": os.path.relpath(
                    image_path(source_manifest, r), Path(destination).resolve().parent
                ),
            },
        }
        for r in rows
    ]
