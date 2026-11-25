import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from gui_trajectory.bundles import bundle_data, bundle_run, release
from gui_trajectory.data import prepare
from gui_trajectory.io import file_digest, image_path, load_manifest, read_json, write_json
from gui_trajectory.operations import merge
from gui_trajectory.runner import generate
from gui_trajectory.team import setup

PROJECT = Path(__file__).resolve().parents[1]


class DistributionTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        images = self.root / "source-images"
        images.mkdir()
        annotations = []
        for i in range(3):
            Image.new("RGB", (100, 100), (i * 50, 100, 150)).save(images / f"{i}.png")
            annotations.append(
                {"image": f"{i}.png", "query": f"Find button {i}", "box": [40, 40, 20, 20]}
            )
        write_json(self.root / "source.json", annotations)
        self.manifest = self.root / "source-manifest.jsonl"
        prepare(
            self.root / "source.json",
            images,
            self.manifest,
            "mapped",
            "synthetic/test",
            "fixture-v1",
            "train",
            {
                "image": "image",
                "instruction": "query",
                "bbox": "box",
                "bbox_format": "xywh",
                "units": "pixels",
            },
        )
        self.bin = self.root / "bin"
        self.bin.mkdir()
        script = (PROJECT / "tests/fake_teacher.py").read_text()
        for teacher in ("codex", "claude"):
            binary = self.bin / teacher
            binary.write_text(f"#!{sys.executable}\n" + script)
            binary.chmod(0o755)
        self.counter = self.root / "calls"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "GUI_TEST_COUNTER": str(self.counter),
            "GUI_TEST_SCENARIO": "success",
        }

    def extract(self, archive, target):
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(target)
        return target / archive.stem

    def test_dataset_archive_survives_move_and_deduplicates_original_images(self):
        path = self.root / "assignment.zip"
        bundle_data(self.manifest, path)
        unpacked = self.extract(path, self.root / "another-machine/data")
        rows = load_manifest(unpacked / "manifest.jsonl")
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(
                file_digest(image_path(unpacked / "manifest.jsonl", row)), row["image"]["sha256"]
            )
            self.assertFalse(Path(row["image"]["path"]).is_absolute())
        for line in (unpacked / "SHA256SUMS.txt").read_text().splitlines():
            sha, name = line.split("  ", 1)
            self.assertEqual(sha, file_digest(unpacked / name))
        with self.assertRaisesRegex(ValueError, "already exists"):
            bundle_data(self.manifest, path)

    def test_modified_images_are_rejected_before_packing(self):
        image_path(self.manifest, load_manifest(self.manifest)[0]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            bundle_data(self.manifest, self.root / "bad.zip")
        self.assertFalse((self.root / "bad.zip").exists())

    def test_independent_submissions_merge_same_samples_from_different_paths(self):
        assignments = self.root / "assignment.zip"
        bundle_data(self.manifest, assignments)
        incoming = []
        from unittest.mock import patch

        with patch.dict(os.environ, self.env):
            for provider in ("codex", "claude"):
                worker = self.extract(assignments, self.root / provider)
                run = worker / "run"
                generate(
                    worker / "manifest.jsonl",
                    provider,
                    None,
                    run,
                    binary=str(self.bin / provider),
                    retries=0,
                )
                # Extra private/diagnostic files must not enter a submission.
                (run / "auth.json").write_text("PRIVATE_CREDENTIAL_SENTINEL")
                (run / "debug.log").write_text("PRIVATE_LOG_SENTINEL")
                scores = run / "review/scores.csv"
                scores.parent.mkdir()
                scores.write_text("job_id,decision\nexample,accept\n")
                archive = self.root / f"{provider}-results.zip"
                bundle_run(run, archive)
                with zipfile.ZipFile(archive) as zipped:
                    names = zipped.namelist()
                    self.assertFalse(any("auth.json" in n or "debug.log" in n for n in names))
                    self.assertFalse(any("attempt-" in n for n in names))
                incoming.append(self.extract(archive, self.root / "incoming"))
                self.assertEqual(
                    (incoming[-1] / "review/scores.csv").read_text(), scores.read_text()
                )
                shutil.rmtree(worker)
        self.assertEqual(merge(incoming, self.root / "merged"), {"samples": 3, "jobs": 6})
        self.assertEqual(len(load_manifest(self.root / "merged/manifest.jsonl")), 3)
        row = load_manifest(incoming[0] / "manifest.jsonl")[0]
        image_path(incoming[0] / "manifest.jsonl", row).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            merge(incoming, self.root / "invalid-merge")

    def test_local_setup_remembers_backend_only_after_success(self):
        with (
            patch("gui_trajectory.team.ROOT", self.root),
            patch("gui_trajectory.team.subprocess.run", return_value=Mock(returncode=0)) as run,
        ):
            self.assertEqual(setup("local"), 0)
            self.assertEqual((self.root / ".pipeline-backend").read_text(), "local\n")
            self.assertEqual(run.call_args_list[0].args[0][1:3], ["-m", "venv"])
            self.assertEqual(run.call_args_list[1].args[0][0], str(self.root / ".venv/bin/python"))
            run.reset_mock()
            self.assertEqual(setup(), 0)
            self.assertEqual(run.call_count, 2)
            run.return_value = Mock(returncode=1)
            self.assertEqual(setup("docker"), 1)
            self.assertEqual((self.root / ".pipeline-backend").read_text(), "local\n")
            run.return_value = Mock(returncode=0)
            self.assertEqual(setup("docker"), 0)
            self.assertEqual((self.root / ".pipeline-backend").read_text(), "docker\n")

    def test_release_and_wrapper_in_clean_extracted_directory_with_spaces(self):
        self.wrapper_workflow("docker")

    def test_local_wrapper_workflow_never_calls_docker(self):
        self.wrapper_workflow("local")

    def wrapper_workflow(self, backend):
        archive = self.root / "software.zip"
        release(PROJECT, archive)
        with zipfile.ZipFile(archive) as zipped:
            names = [n.split("/", 1)[1] for n in zipped.namelist()]
            self.assertFalse(
                any(n.startswith(("data/", "runs/", ".codex/", ".agent/", ".team/")) for n in names)
            )
            self.assertNotIn("job.json", names)
            self.assertEqual(
                [n for n in names if n.startswith(".claude/")],
                [".claude/skills/사용법/SKILL.md"],
            )
            for relative in (
                "SKILL.md",
                "agents/openai.yaml",
                "references/coordinator.md",
                "references/worker.md",
            ):
                self.assertIn(f".agents/skills/gui-trajectory-usage/{relative}", names)
            self.assertIn("QUICKSTART.md", names)
            self.assertIn("requirements-local.txt", names)
            self.assertIn("apps-script/Code.gs", names)
            self.assertIn("docs/shared-assignment.md", names)
            self.assertIn("docs/screenspot-team-run.md", names)
            self.assertFalse(any(n.startswith(".venv/") or n == ".pipeline-backend" for n in names))
            self.assertIn("examples/demo/images/toolbar.png", names)
            self.assertEqual(zipped.getinfo("software/team").external_attr >> 16 & 0o111, 0o111)
            self.assertEqual(
                zipped.read("software/README.md"), (PROJECT / "QUICKSTART.md").read_bytes()
            )
        project = self.extract(archive, self.root / "a teammate with spaces")
        # Python's ZipFile does not restore executable bits; common unzip utilities do.
        for name in ("team", "pipeline"):
            (project / name).chmod(0o755)
        assignments = self.root / "assignment.zip"
        bundle_data(self.manifest, assignments)
        self.extract(assignments, project / "data")
        # Emulate Docker's CLI routing, while exercising real wrapper/runner subprocesses.
        docker = self.bin / "docker"
        docker.write_text(
            f"#!{sys.executable}\nimport os,sys\na=sys.argv[1:]\n"
            "if a[0]=='build': raise SystemExit(0)\n"
            "i=a.index('gui-trajectory:0.1')\n"
            "os.execv(sys.executable,[sys.executable,'-m','gui_trajectory',*a[i+1:]])\n"
        )
        docker.chmod(0o755)

        def invoke(*args, expected=0):
            result = subprocess.run(
                [str(project / "team"), *args],
                cwd=self.root,
                env=self.env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            return result.stdout if expected == 0 else result.stdout + result.stderr

        if backend == "docker":
            invoke("setup")
        else:
            # Exercise actual local subprocess routing, with test dependencies already installed.
            # Environment creation and backend persistence are checked separately above.
            local_python = project / ".venv/bin/python"
            local_python.parent.mkdir(parents=True)
            local_python.symlink_to(sys.executable)
            selection = project / ".pipeline-backend"
            selection.write_text("local\n")
            docker.write_text("#!/bin/sh\necho 'Unexpected Docker call' >&2\nexit 99\n")
            converted = subprocess.run(
                [
                    str(project / "pipeline"),
                    "prepare",
                    "--adapter",
                    "mapped",
                    "--annotations",
                    str(project / "examples/demo/annotations.json"),
                    "--image-root",
                    str(project / "examples/demo/images"),
                    "--mapping",
                    str(project / "examples/demo/mapping.json"),
                    "--dataset",
                    "synthetic/demo",
                    "--revision",
                    "test",
                    "--role",
                    "pilot_dev",
                    "--output",
                    str(project / "data/demo/manifest.jsonl"),
                ],
                cwd=project,
                env=self.env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(converted.returncode, 0, converted.stdout + converted.stderr)
            self.assertEqual(len(load_manifest(project / "data/demo/manifest.jsonl")), 2)
        for provider in ("codex", "claude"):
            config = f"jobs/{provider}.json"
            options = ("--config", config)
            invoke(
                *options,
                "init",
                "--provider",
                provider,
                "--manifest",
                "data/assignment/manifest.jsonl",
            )
            invoke(
                *options,
                "init",
                "--provider",
                provider,
                "--manifest",
                "data/assignment/manifest.jsonl",
                expected=2,
            )
            invoke(*options, "doctor")
            previous_calls = self.counter.read_text() if self.counter.exists() else None
            output = invoke(*options, "plan")
            self.assertTrue(json.loads(output)["dry_run"])
            self.assertEqual(
                self.counter.read_text() if self.counter.exists() else None, previous_calls
            )
            invoke(*options, "run", "--limit", "1")
            invoke(*options, "run")
            output = invoke(*options, "run")
            self.assertEqual(json.loads(output)["skipped"], 3)
            invoke(*options, "status")
            invoke(*options, "review")
            self.assertTrue((project / f"runs/{provider}/review/review.html").is_file())
            invoke(*options, "submit")
            invoke(*options, "submit", expected=2)
            saved = project / f"dist/{provider}-results.zip"
            self.assertEqual(
                read_json(project / f"runs/{provider}/run.json")["config"]["model"], "cli_default"
            )
            self.assertTrue(saved.is_file())
        self.assertEqual(self.counter.read_text(), "6")
        if backend == "local":
            selection.write_text("invalid\n")
            self.assertIn(
                "실행 환경 설정 오류", invoke("--config", "jobs/codex.json", "status", expected=2)
            )
            selection.write_text("local\n")
            local_python.unlink()
            self.assertIn(
                "setup --backend local", invoke("--config", "jobs/codex.json", "status", expected=2)
            )
        invoke("--config", "jobs/codex.json", "run", "--limit", "0", expected=2)
        config = project / "jobs/codex.json"
        changed = read_json(config)
        changed["provider"] = "arbitrary-shell-command"
        write_json(config, changed)
        invoke("--config", "jobs/codex.json", "plan", expected=2)
        changed["provider"] = "codex"
        changed["manifest"] = str(self.manifest)
        write_json(config, changed)
        invoke("--config", "jobs/codex.json", "plan", expected=2)
        checks = project / "SHA256SUMS.txt"
        # Packaged checksums cover bytes, independently of execution permissions.
        for line in checks.read_text().splitlines():
            sha, name = line.split("  ", 1)
            if name.startswith("jobs/"):
                continue
            self.assertEqual(sha, hashlib.sha256((project / name).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
