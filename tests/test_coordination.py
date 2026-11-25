import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from gui_trajectory import coordination
from gui_trajectory.campaign import build_campaign, create_campaign, load_campaign
from gui_trajectory.data import prepare
from gui_trajectory.io import load_manifest, read_json, write_json, write_jsonl

PROJECT = Path(__file__).resolve().parents[1]


class CoordinationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "worker with spaces"
        self.root.mkdir()
        for folder in ("src", "examples", "tests"):
            shutil.copytree(PROJECT / folder, self.root / folder)
        for name in ("team", "pipeline"):
            shutil.copy2(PROJECT / name, self.root / name)
        self.manifest = self.root / "data/full.jsonl"
        prepare(
            self.root / "examples/demo/annotations.json",
            self.root / "examples/demo/images",
            self.manifest,
            "mapped",
            "synthetic/demo",
            "fixture",
            "pilot_dev",
            read_json(self.root / "examples/demo/mapping.json"),
        )
        self.campaign = self.root / "data/campaign.json"
        create_campaign(self.manifest, self.campaign, "demo", batch_size=1)
        self.config = self.root / "job.json"
        self.events = []
        self.status = "available"
        self.claim = "fixture-claim-12345678"
        self.offline = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.events.append(payload)
                if owner.offline:
                    self.send_response(503)
                    self.end_headers()
                    return
                response = {"ok": payload["key"] == "fixture-key"}
                if payload["action"] == "acquire":
                    response["assignment"] = {"batch_id": "0000", "claim": owner.claim}
                if payload["action"] == "update":
                    owner.status = payload["status"]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.url = f"http://127.0.0.1:{server.server_port}/exec"

    def join(self):
        return coordination.join(
            self.root,
            self.config,
            self.campaign,
            self.manifest,
            self.url,
            "alice",
            "codex",
            "fixture-key",
        )

    def test_catalog_reproducible_across_order_paths_and_never_splits_a_screen(self):
        first = load_campaign(self.campaign, self.manifest)
        # Both demo targets use the same screen; target size 1 must retain both together.
        self.assertEqual(len(first["batches"]), 1)
        rows = list(reversed(load_manifest(self.manifest)))
        elsewhere = self.root / "data/elsewhere.jsonl"
        write_jsonl(elsewhere, rows)
        self.assertEqual(build_campaign(elsewhere, "demo", batch_size=1), first)
        rows[0]["instruction"] = "Different task"
        write_jsonl(elsewhere, rows)
        with self.assertRaisesRegex(ValueError, "differs"):
            load_campaign(self.campaign, elsewhere)

    def test_join_acquire_retry_and_recover_interrupted_config_creation(self):
        self.join()
        first = coordination.acquire(self.root, self.config)
        self.assertEqual(first["samples"], 2)
        second = coordination.acquire(self.root, self.config)
        self.assertTrue(second["resumed"])
        path = coordination.state_path(self.root, self.config)
        state = read_json(path)
        state["assignment"]["ready"] = False
        coordination.save_state(path, state)
        self.config.unlink()
        coordination.acquire(self.root, self.config)
        self.assertTrue(self.config.is_file())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, "이미"):
            self.join()

    def test_batches_cover_every_input_once_across_multiple_screen_groups(self):
        images = self.root / "data/multiple"
        images.mkdir()
        annotations = []
        for index in range(8):
            Image.new("RGB", (100, 100), (index * 20, 80, 120)).save(images / f"{index}.png")
            for label in ("Save", "Cancel"):
                annotations.append(
                    {"image": f"{index}.png", "query": label, "box": [20, 20, 20, 20]}
                )
        write_json(images / "annotations.json", annotations)
        manifest = self.root / "data/multiple.jsonl"
        prepare(
            images / "annotations.json",
            images,
            manifest,
            "mapped",
            "synthetic/multi",
            "fixture",
            "train",
            {
                "image": "image",
                "instruction": "query",
                "bbox": "box",
                "bbox_format": "xywh",
                "units": "pixels",
            },
        )
        catalog = build_campaign(manifest, "multiple", batch_size=3)
        ids = [sample for batch in catalog["batches"] for sample in batch["sample_ids"]]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(set(ids)), 16)
        self.assertEqual(set(ids), {r["sample_id"] for r in load_manifest(manifest)})
        self.assertEqual(len(catalog["batches"]), 8)
        counted = build_campaign(manifest, "counted", batch_count=3)
        self.assertEqual(sorted(len(b["sample_ids"]) for b in counted["batches"]), [4, 6, 6])
        owners = {sample: b["batch_id"] for b in counted["batches"] for sample in b["sample_ids"]}
        self.assertEqual(len(owners), 16)
        screen_owners = {}
        for row in load_manifest(manifest):
            screen_owners.setdefault(row["group_id"], set()).add(owners[row["sample_id"]])
        self.assertTrue(all(len(owners) == 1 for owners in screen_owners.values()))
        output = self.root / "data/count8.json"
        result = create_campaign(manifest, output, "eight", batch_count=8)
        self.assertEqual(result["sizes"], [2] * 8)
        self.assertEqual(result["tasks"], 16)
        self.assertEqual(load_campaign(output, manifest)["partition_version"], 2)
        write_jsonl(manifest, list(reversed(load_manifest(manifest))))
        self.assertEqual(build_campaign(manifest, "eight", batch_count=8), load_campaign(output))
        for invalid in (0, -1, 9):
            with self.assertRaises(ValueError):
                build_campaign(manifest, "invalid", batch_count=invalid)

    def test_offline_progress_durable_and_no_offline_allocation(self):
        self.join()
        coordination.acquire(self.root, self.config)
        self.offline = True
        with self.assertRaises(coordination.OfflineError):
            coordination.acquire(self.root, self.config)
        result = coordination.synchronize(self.root, self.config, phase="paused")
        self.assertFalse(result["synced"])
        self.assertTrue(coordination.load_state(self.root, self.config)["pending_sync"])
        self.offline = False
        self.assertTrue(coordination.synchronize(self.root, self.config)["synced"])
        self.assertFalse(coordination.load_state(self.root, self.config)["pending_sync"])

    def test_modified_job_rejected_and_session_lock_prevents_overlapping_commands(self):
        self.join()
        coordination.acquire(self.root, self.config)
        with coordination.session_lock(self.root, self.config):
            with self.assertRaisesRegex(ValueError, "실행 중"):
                with coordination.session_lock(self.root, self.config):
                    pass
        job = read_json(self.config)
        job["model"] = "different-model"
        write_json(self.config, job)
        with self.assertRaisesRegex(ValueError, "변경"):
            coordination.synchronize(self.root, self.config)

    def test_rejected_request_never_echoes_key(self):
        with self.assertRaises(ValueError) as caught:
            coordination.request(self.url, "PRIVATE_KEY_SENTINEL", "status")
        self.assertNotIn("PRIVATE_KEY_SENTINEL", str(caught.exception))

    def test_worker_commands_update_sheet_without_manual_editing(self):
        environment = {
            **os.environ,
            "GUI_TEAM_KEY": "fixture-key",
            "GUI_TEST_COUNTER": str(self.root / "calls"),
            "GUI_TEST_SCENARIO": "success",
        }
        binary = self.root / "fake-bin"
        binary.mkdir()
        teacher = binary / "codex"
        teacher.write_text(
            f"#!{sys.executable}\n" + (PROJECT / "tests/fake_teacher.py").read_text()
        )
        teacher.chmod(0o755)
        environment["PATH"] = str(binary) + ":" + os.environ["PATH"]
        local_python = self.root / ".venv/bin/python"
        local_python.parent.mkdir(parents=True)
        local_python.symlink_to(sys.executable)
        (self.root / ".pipeline-backend").write_text("local\n")
        # Any Docker invocation is a regression in this workflow.
        docker = binary / "docker"
        docker.write_text("#!/bin/sh\nexit 99\n")
        docker.chmod(0o755)

        def run(*args):
            result = subprocess.run(
                [str(self.root / "team"), *args],
                cwd=self.root,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("fixture-key", result.stdout + result.stderr)
            return result.stdout

        run("register", "--campaign", "data/campaign.json", "--url", self.url)
        run(
            "join",
            "--campaign",
            "data/campaign.json",
            "--manifest",
            "data/full.jsonl",
            "--url",
            self.url,
            "--worker",
            "alice",
            "--provider",
            "codex",
        )
        run("acquire")
        run("plan")
        run("run", "--limit", "1")
        self.assertEqual(self.status, "paused")
        self.offline = True
        run("run")
        self.assertTrue(coordination.load_state(self.root, self.config)["pending_sync"])
        self.offline = False
        run("sync")
        self.assertEqual(self.status, "generated")
        run("review")
        run("submit", "--result-url", "https://drive.google.com/example")
        self.assertEqual(self.status, "submitted")
        last = self.events[-1]
        self.assertEqual(last["completed"], 2)
        self.assertEqual(last["result_url"], "https://drive.google.com/example")
        self.assertTrue(last["archive"]["name"].endswith(".zip"))
        self.assertEqual(len(last["archive"]["sha256"]), 64)
        self.assertEqual((self.root / "calls").read_text(), "2")
        self.assertTrue(
            any(e["action"] == "update" and e["status"] == "running" for e in self.events)
        )
        run("run")  # A repeated command must not downgrade a submitted task.
        run("sync")
        self.assertEqual(self.status, "submitted")
        self.assertEqual((self.root / "calls").read_text(), "2")
        # Submission archives cannot contain participation credentials or coordination state.
        import zipfile

        for archive in (self.root / "dist").glob("*.zip"):
            with zipfile.ZipFile(archive) as zipped:
                self.assertFalse(any("/.team/" in n for n in zipped.namelist()))


if __name__ == "__main__":
    unittest.main()
