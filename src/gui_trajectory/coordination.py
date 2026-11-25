"""Google Apps Script coordination; host standard library only, no teacher credentials."""

import fcntl
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager

from .campaign import load_campaign, manifest_identity
from .data import relocate
from .io import digest, load_manifest, read_json, write_json, write_jsonl
from .review import results


class OfflineError(ValueError):
    pass


def request(endpoint, key, action, **payload):
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")
    ):
        raise ValueError("배정 서비스는 HTTPS 주소를 사용하세요.")
    body = json.dumps({"action": action, "key": key, **payload}).encode()
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise OfflineError(
            "배정 서비스 연결 실패. URL, 배포 접근 설정과 네트워크를 확인하세요."
        ) from exc
    if not isinstance(data, dict) or not data.get("ok"):
        # Do not echo remote responses: they can include request parameters or secrets.
        raise ValueError("배정 요청 거절. 참여 코드, 실험 버전 또는 작업 소유권을 확인하세요.")
    return data


def state_path(root, config):
    return root / ".team" / (digest(str(config.resolve().relative_to(root)))[:24] + ".json")


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(path, state)
    path.chmod(0o600)


@contextmanager
def session_lock(root, config):
    path = state_path(root, config).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("같은 설정의 team 명령이 실행 중입니다.") from exc
        yield


def join(root, config, campaign, manifest, endpoint, worker, provider, key):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", worker):
        raise ValueError("팀원 이름은 영문, 숫자, _, -로 1-64자입니다.")
    path = state_path(root, config)
    if path.exists() or config.exists():
        raise ValueError(
            "이미 설정이 있습니다. 기존 설정을 사용하거나 --config로 다른 이름을 지정하세요."
        )
    catalog = load_campaign(campaign, manifest)
    if provider not in catalog["providers"]:
        raise ValueError("이 실험에서 사용하지 않는 교사입니다.")
    request(
        endpoint,
        key,
        "status",
        campaign_id=catalog["campaign_id"],
        fingerprint=catalog["fingerprint"],
    )
    stored = root / ".team/catalogs" / (catalog["fingerprint"] + ".json")
    write_json(stored, catalog)
    state = {
        "endpoint": endpoint,
        "key": key,
        "worker": worker,
        "provider": provider,
        "catalog": str(stored.relative_to(root)),
        "manifest": str(manifest.relative_to(root)),
        "assignment": None,
    }
    save_state(path, state)
    return {"joined": True, "worker": worker, "provider": provider, "next": "./team acquire"}


def load_state(root, config):
    return read_json(state_path(root, config))


def remote(state, catalog, action, **payload):
    return request(
        state["endpoint"],
        state["key"],
        action,
        campaign_id=catalog["campaign_id"],
        fingerprint=catalog["fingerprint"],
        worker=state["worker"],
        provider=state["provider"],
        **payload,
    )


def acquire(root, config):
    path = state_path(root, config)
    state = read_json(path)
    catalog = load_campaign(root / state["catalog"], root / state["manifest"])
    if state["assignment"] and state["assignment"].get("ready"):
        # Flush deferred completion first. Offline acquisition is forbidden.
        synchronize(root, config, strict=True)
        state = read_json(path)
    response = remote(state, catalog, "acquire")
    assigned = response.get("assignment")
    if assigned is None:
        return {"available": False, "message": "가져올 미배정 작업이 없습니다."}
    batch_id, claim = assigned["batch_id"], assigned["claim"]
    if not re.fullmatch(r"[0-9]{4,}", batch_id) or not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", claim):
        raise ValueError("잘못된 배정 응답입니다.")
    batch = next(item for item in catalog["batches"] if item["batch_id"] == batch_id)
    old = state["assignment"]
    if old and old["claim"] == claim and old.get("ready"):
        validate_assignment(root, config, state, catalog)
        return {"resumed": True, "batch": batch_id, "samples": len(batch["sample_ids"])}
    directory = root / "runs" / catalog["campaign_id"] / state["provider"] / f"{batch_id}-{claim}"
    manifest = root / ".team/inputs" / f"{claim}.jsonl"
    selected = set(batch["sample_ids"])
    rows = [row for row in load_manifest(root / state["manifest"]) if row["sample_id"] in selected]
    rows.sort(key=lambda row: row["sample_id"])
    write_jsonl(manifest, relocate(rows, root / state["manifest"], manifest))
    state["assignment"] = {
        "batch_id": batch_id,
        "claim": claim,
        "phase": "reserved",
        "ready": False,
    }
    # Save the reservation first. A retry recovers the same server-side claim after interruption.
    save_state(path, state)
    write_json(
        config,
        {
            "schema_version": 1,
            "provider": state["provider"],
            "manifest": os.path.relpath(manifest, config.parent),
            "output": os.path.relpath(directory, config.parent),
            "model": None,
            "timeout": 300,
            "retries": 1,
        },
    )
    state["assignment"]["ready"] = True
    save_state(path, state)
    return {
        "batch": batch_id,
        "provider": state["provider"],
        "samples": len(rows),
        "next": "./team run",
    }


def validate_assignment(root, config, state=None, catalog=None):
    state = state or load_state(root, config)
    catalog = catalog or load_campaign(root / state["catalog"])
    assignment = state["assignment"]
    if not assignment:
        raise ValueError("먼저 ./team acquire로 작업을 받으세요.")
    job = read_json(config)
    batch = next(b for b in catalog["batches"] if b["batch_id"] == assignment["batch_id"])
    rows = load_manifest(config.parent / job["manifest"])
    source = load_manifest(root / state["manifest"])
    if manifest_identity(source) != catalog["manifest_identity"]:
        raise ValueError("전체 데이터 manifest가 변경되었습니다.")
    selected = set(batch["sample_ids"])
    expected = [r for r in source if r["sample_id"] in selected]
    output = (
        root
        / "runs"
        / catalog["campaign_id"]
        / state["provider"]
        / f"{assignment['batch_id']}-{assignment['claim']}"
    )
    if (
        manifest_identity(rows) != manifest_identity(expected)
        or job["provider"] != state["provider"]
        or job.get("model") is not None
        or (config.parent / job["output"]).resolve() != output
    ):
        raise ValueError("배정된 입력, 교사 또는 결과 경로가 변경되었습니다.")
    return job, batch


def progress(root, config, state):
    job, batch = validate_assignment(root, config, state)
    expected = set(batch["sample_ids"])
    saved = results(config.parent / job["output"])
    by_sample = {}
    for result in saved:
        if result["sample_id"] not in expected or result["sample_id"] in by_sample:
            raise ValueError("배정과 일치하지 않거나 중복된 생성 결과입니다.")
        by_sample[result["sample_id"]] = result
    completed = sum(r["state"] == "completed" for r in saved)
    failed = len(saved) - completed
    valid = sum(
        r["state"] == "completed" and r.get("validation", {}).get("valid", False) for r in saved
    )
    total = len(expected)
    phase = state["assignment"]["phase"]
    if phase == "submitted" and completed == total:
        status = "submitted"
    elif completed == total:
        status = "generated"
    elif phase == "running":
        status = "running"
    else:
        status = "paused" if saved else "reserved"
    return {"completed": completed, "failed": failed, "valid": valid, "status": status}


def synchronize(root, config, *, phase=None, archive=None, result_url=None, strict=False):
    path = state_path(root, config)
    state = read_json(path)
    if not state["assignment"]:
        return {"synced": True}
    keep_submission = (
        state["assignment"]["phase"] == "submitted"
        and progress(root, config, state)["status"] == "submitted"
    )
    if phase and not keep_submission:
        state["assignment"]["phase"] = phase
    if archive:
        state["assignment"]["archive"] = archive
    if result_url is not None:
        state["assignment"]["result_url"] = result_url
    state["pending_sync"] = True
    save_state(path, state)
    payload = progress(root, config, state)
    assignment = state["assignment"]
    try:
        catalog = load_campaign(root / state["catalog"])
        remote(
            state,
            catalog,
            "update",
            batch_id=assignment["batch_id"],
            claim=assignment["claim"],
            **payload,
            archive=assignment.get("archive", {}),
            result_url=assignment.get("result_url", ""),
        )
    except OfflineError:
        if strict:
            raise
        print(
            "시트 연결이 끊겼습니다. 로컬 작업을 유지하며 다음 실행에서 자동 동기화합니다.",
            file=sys.stderr,
        )
        return {"synced": False, **payload}
    state["pending_sync"] = False
    save_state(path, state)
    return {"synced": True, **payload}


def heartbeat(root, config):
    last = 0.0

    def update():
        nonlocal last
        now = time.monotonic()
        if now - last >= 30:
            synchronize(root, config)
            last = now

    return update


def relinquish(root, config):
    state = load_state(root, config)
    catalog = load_campaign(root / state["catalog"])
    if not state["assignment"]:
        raise ValueError("반납할 배정이 없습니다.")
    current = progress(root, config, state)
    if current["completed"] or current["failed"]:
        raise ValueError(
            "생성 결과가 있는 작업은 반납할 수 없습니다. 재개하거나 담당자에게 알려주세요."
        )
    remote(
        state,
        catalog,
        "release",
        batch_id=state["assignment"]["batch_id"],
        claim=state["assignment"]["claim"],
    )
    state["assignment"] = None
    save_state(state_path(root, config), state)
    config.unlink(missing_ok=True)
    return {"released": True}
