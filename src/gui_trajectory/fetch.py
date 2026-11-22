"""Optional official ScreenSpot-v2 download, pinned to a resolved Hub revision."""

import json
import shutil
import stat
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from .io import file_digest, read_json, write_json

REPOSITORY = "OS-Copilot/ScreenSpot-v2"


def extract_images(archive, destination, flatten=False):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as zipped:
        if sum(i.file_size for i in zipped.infolist()) > 20 * 1024**3:
            raise ValueError("Image archive exceeds the extraction size limit")
        names = set()
        for item in zipped.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination) or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Unsafe archive member")
            if item.is_dir():
                continue
            if target.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            if flatten:
                target = destination / target.name
                if target.name in names:
                    raise ValueError("Duplicate flattened image filename")
                names.add(target.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(item) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def fetch_screenspot(destination, revision="main"):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    encoded_revision = urllib.parse.quote(revision, safe="")
    api = f"https://huggingface.co/api/datasets/{REPOSITORY}/revision/{encoded_revision}"
    with urllib.request.urlopen(api, timeout=60) as response:
        resolved = json.load(response)["sha"]
    files = [f"screenspot_{domain}_v2.json" for domain in ("mobile", "desktop", "web")]
    files.append("screenspotv2_image.zip")
    prior = read_json(destination / "source.json") if (destination / "source.json").exists() else {}
    hashes = {}
    for name in files:
        target = destination / name
        expected = prior.get("sha256", {}).get(name)
        if prior.get("revision") == resolved and target.is_file() and expected:
            if file_digest(target) == expected:
                hashes[name] = expected
                continue
        url = f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{resolved}/{name}"
        temporary = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        temporary.replace(target)
        hashes[name] = file_digest(target)
    extract_images(destination / files[-1], destination / "images", flatten=True)
    source = {"dataset": REPOSITORY, "revision": resolved, "sha256": hashes}
    write_json(destination / "source.json", source)
    return source
