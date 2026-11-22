import csv
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image, PngImagePlugin

from gui_trajectory.data import normalize_answer, prepare, screen_groups, select_pilot
from gui_trajectory.fetch import extract_images
from gui_trajectory.io import image_path, load_manifest, read_json, read_jsonl, write_json
from gui_trajectory.operations import merge, shard
from gui_trajectory.providers import subscription_env
from gui_trajectory.review import export, review
from gui_trajectory.runner import generate
from gui_trajectory.validation import validate_output


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.images = self.root / "images"
        self.images.mkdir()
        self.annotations = self.root / "screenspot_desktop_v2.json"
        self.manifest = self.root / "manifest.jsonl"
        self.counter = self.root / "calls"
        script = Path(__file__).with_name("fake_teacher.py").read_text()
        self.fake = self.root / "teacher"
        self.fake.write_text(f"#!{sys.executable}\n" + script)
        self.fake.chmod(0o755)
        self.env = patch.dict(
            os.environ, {"GUI_TEST_COUNTER": str(self.counter), "GUI_TEST_SCENARIO": "success"}
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def prepare_samples(self, count=2, role="pilot_dev"):
        records = []
        for index in range(count):
            filename = f"screen-{index}.png"
            Image.new("RGB", (100, 100), (index, 50, 100)).save(self.images / filename)
            records.append(
                {
                    "img_filename": filename,
                    "instruction": f"Find button {index}",
                    "bbox": [40, 40, 20, 20],
                    "data_type": "text",
                }
            )
        write_json(self.annotations, records)
        return prepare(
            self.annotations,
            self.images,
            self.manifest,
            "screenspot_v2",
            "OS-Copilot/ScreenSpot-v2",
            "test-revision",
            role,
        )

    def run_teacher(self, provider="codex", directory="run", **kwargs):
        return generate(
            self.manifest,
            provider,
            "explicit-test-model",
            self.root / directory,
            binary=str(self.fake),
            retries=0,
            **kwargs,
        )

    def accept_sheet(self, directory):
        report = self.root / directory / "review"
        review(self.root / directory, report)
        path = report / "scores.csv"
        with path.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            row.update(
                evidence="2",
                target_match="2",
                usefulness="2",
                consistency="2",
                decision="accept",
                reviewer="test-reviewer",
            )
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_screenspot_xywh_and_provenance(self):
        self.assertEqual(self.prepare_samples()["valid"], 2)
        row = load_manifest(self.manifest)[0]
        self.assertEqual(row["answer"]["bbox"], [0.4, 0.4, 0.6, 0.6])
        self.assertEqual(row["answer"]["point"], [0.5, 0.5])
        self.assertEqual(row["answer"]["original"]["bbox"], [40, 40, 20, 20])
        self.assertTrue(image_path(self.manifest, row).is_file())
        self.assertEqual(row["role"], "pilot_dev")

    def test_screenspot_cannot_be_training_data(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.prepare_samples(role="train")

    def test_mapped_dataset_nested_schema(self):
        Image.new("RGB", (200, 100)).save(self.images / "example.png")
        write_json(
            self.annotations,
            {
                "samples": [
                    {
                        "screen": {"path": "example.png"},
                        "query": "Click save",
                        "box": [100, 50, 160, 90],
                    }
                ]
            },
        )
        mapping = {
            "records_path": "samples",
            "image": "screen.path",
            "instruction": "query",
            "bbox": "box",
            "units": "pixels",
            "bbox_format": "xyxy",
        }
        prepare(
            self.annotations, self.images, self.manifest, "mapped", "custom", "r1", "train", mapping
        )
        row = load_manifest(self.manifest)[0]
        self.assertEqual(row["answer"]["point"], [0.65, 0.7])
        self.assertEqual(row["attributes"]["element_type"], "unknown")

    def test_invalid_boxes_do_not_silently_clamp(self):
        for box in ([10, 10, -5, 2], [90, 10, 20, 20], [True, 2, 3, 4], [0, 0, float("nan"), 1]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                normalize_answer(
                    {"bbox": box},
                    {"bbox": "bbox", "bbox_format": "xywh", "units": "pixels"},
                    (100, 100),
                )

    def test_point_only_does_not_invent_box(self):
        answer = normalize_answer({"xy": [400, 700]}, {"point": "xy", "units": "1000"}, (800, 500))
        self.assertIsNone(answer["bbox"])
        self.assertEqual(answer["point"], [0.4, 0.7])

    def test_corrupt_images_and_escape_paths_reported(self):
        write_json(
            self.annotations,
            [
                {"img_filename": "../escape.png", "instruction": "bad"},
                {"img_filename": "missing.png", "instruction": "bad"},
            ],
        )
        summary = prepare(
            self.annotations,
            self.images,
            self.manifest,
            "screenspot_v2",
            "source",
            "revision",
            "pilot_dev",
        )
        self.assertEqual(summary["invalid"], 2)
        self.assertFalse(load_manifest(self.manifest))

    def test_same_pixels_with_different_png_metadata_are_grouped(self):
        self.prepare_samples()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("note", "second encoding")
        with Image.open(self.images / "screen-0.png") as image:
            image.save(self.images / "screen-1.png", pnginfo=metadata)
        prepare(
            self.annotations,
            self.images,
            self.manifest,
            "screenspot_v2",
            "source",
            "r1",
            "pilot_dev",
        )
        rows = load_manifest(self.manifest)
        self.assertNotEqual(rows[0]["image"]["sha256"], rows[1]["image"]["sha256"])
        self.assertEqual(rows[0]["group_id"], rows[1]["group_id"])

    def test_pilot_30_balanced_and_deterministic(self):
        self.prepare_samples(36)
        rows = load_manifest(self.manifest)
        for index, row in enumerate(rows):
            row["attributes"] = {
                "platform": ("mobile", "desktop", "web")[index // 12],
                "element_type": "text" if index % 2 else "icon",
            }
        first, counts = select_pilot(rows)
        second, _ = select_pilot(list(reversed(rows)))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 30)
        self.assertEqual(set(counts.values()), {5})
        self.assertEqual(len({row["group_id"] for row in first}), 30)

    def test_pilot_shortage_fails_instead_of_duplicating(self):
        self.prepare_samples()
        with self.assertRaisesRegex(ValueError, "distinct"):
            select_pilot(load_manifest(self.manifest), 30)

    def test_screen_groups_join_pixel_duplicates_and_original_ids(self):
        self.prepare_samples(3)
        rows = load_manifest(self.manifest)
        rows[0]["source_group"] = "same-original"
        rows[1]["source_group"] = "same-original"
        rows[2]["group_id"] = rows[1]["group_id"]
        rows[2]["source_group"] = "different-source-id"
        groups = screen_groups(rows)
        self.assertEqual(len(set(groups.values())), 1)

    def test_dry_run_never_uses_teacher_or_auth(self):
        self.prepare_samples()
        result = generate(self.manifest, "codex", "chosen-model", self.root / "run", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertFalse(self.counter.exists())
        self.assertFalse((self.root / "run").exists())

    def test_default_model_generation_does_not_require_a_name(self):
        self.prepare_samples(1)
        result = generate(
            self.manifest, "codex", None, self.root / "default", binary=str(self.fake), retries=0
        )
        self.assertEqual(result["generated"], 1)
        self.assertEqual(
            read_json(self.root / "default/run.json")["config"]["model"], "cli_default"
        )

    def test_timeout_is_recorded_without_leaving_a_live_child(self):
        self.prepare_samples(1)
        with patch.dict(os.environ, {"GUI_TEST_SCENARIO": "timeout"}):
            result = self.run_teacher(timeout=0.1)
        self.assertEqual(result["failed"], 1)
        saved = next((self.root / "run").glob("jobs/*/result.json"))
        self.assertEqual(read_json(saved)["error"]["kind"], "timeout")

    def test_codex_generation_resumes_and_keeps_private_events_out(self):
        self.prepare_samples()
        first = self.run_teacher(limit=1)
        self.assertEqual(first["generated"], 1)
        second = self.run_teacher()
        self.assertEqual(second["generated"], 1)
        self.assertEqual(second["skipped"], 1)
        self.assertEqual(self.counter.read_text(), "2")
        for path in (self.root / "run").rglob("*.json"):
            self.assertNotIn("PRIVATE_REASONING_SENTINEL", path.read_text())
            self.assertNotIn("private@example.com", path.read_text())

    def test_resume_rejects_changed_model_or_manifest(self):
        self.prepare_samples()
        self.run_teacher(limit=1)
        with self.assertRaisesRegex(ValueError, "settings"):
            generate(
                self.manifest, "codex", "another-model", self.root / "run", binary=str(self.fake)
            )

    def test_quota_halts_then_can_resume(self):
        self.prepare_samples()
        with patch.dict(os.environ, {"GUI_TEST_SCENARIO": "limit"}):
            result = self.run_teacher()
        self.assertEqual(result["halted"], "limit")
        self.assertEqual(self.counter.read_text(), "1")
        result = self.run_teacher()
        self.assertEqual(result["generated"], 2)
        attempts = list((self.root / "run").glob("jobs/*/attempt-*.json"))
        self.assertEqual(len(attempts), 3)

    def test_claude_must_read_actual_image(self):
        self.prepare_samples(1)
        with patch.dict(os.environ, {"GUI_TEST_SCENARIO": "no_image"}):
            result = self.run_teacher("claude")
        self.assertEqual(result["failed"], 1)
        saved = next((self.root / "run").glob("jobs/*/result.json"))
        self.assertEqual(read_json(saved)["error"]["kind"], "image_delivery")

    def test_tools_are_audited_for_both_teachers(self):
        self.prepare_samples(1)
        for provider in ("codex", "claude"):
            with (
                self.subTest(provider=provider),
                patch.dict(os.environ, {"GUI_TEST_SCENARIO": "tool"}),
            ):
                result = self.run_teacher(provider, directory=provider)
                self.assertEqual(result["failed"], 1)

    def test_claude_generation_and_secret_environment_filter(self):
        self.prepare_samples(1)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "SECRET", "OPENAI_API_KEY": "SECRET"}):
            result = self.run_teacher("claude")
            self.assertNotIn("ANTHROPIC_API_KEY", subscription_env())
        self.assertEqual(result["generated"], 1)
        saved = next((self.root / "run").glob("jobs/*/result.json"))
        self.assertTrue(read_json(saved)["validation"]["valid"])
        self.assertNotIn("PRIVATE_IMAGE", saved.read_text())

    def test_output_checks_coordinates_not_just_schema(self):
        self.prepare_samples(1)
        sample = load_manifest(self.manifest)[0]
        response = {
            "status": "ok",
            "visual_steps": ["Visible save icon."],
            "final_click": {"x": 0.1, "y": 0.1},
            "review_reason": "",
        }
        self.assertFalse(validate_output(response, sample)["valid"])
        response["status"] = "needs_review"
        response["visual_steps"] = []
        response["final_click"] = None
        response["review_reason"] = "The reference target is not visible."
        self.assertTrue(validate_output(response, sample)["valid"])

    def test_changed_image_rejected_before_inference(self):
        self.prepare_samples(1)
        Image.new("RGB", (100, 100), "red").save(self.images / "screen-0.png")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_teacher()
        self.assertFalse(self.counter.exists())

    def test_review_preserves_scores_and_export_rejects_pilot_by_default(self):
        self.prepare_samples(1)
        self.run_teacher()
        scores = self.accept_sheet("run")
        original = scores.read_text()
        review(self.root / "run", scores.parent)
        self.assertEqual(scores.read_text(), original)
        with self.assertRaisesRegex(ValueError, "Non-training"):
            export(self.root / "run", scores, self.root / "expert.jsonl")
        result = export(self.root / "run", scores, self.root / "expert.jsonl", allow_pilot=True)
        self.assertEqual(result["exported"], 1)
        row = read_jsonl(self.root / "expert.jsonl")[0]
        self.assertTrue(row["exclude_from_training"])
        self.assertEqual(row["role"], "pilot_dev")

    def test_shards_preserve_group_and_relative_paths(self):
        self.prepare_samples(5)
        shard(self.manifest, self.root / "shards", 2)
        groups = []
        for path in sorted((self.root / "shards").glob("*.jsonl")):
            rows = load_manifest(path)
            groups.append({r["group_id"] for r in rows})
        self.assertFalse(groups[0] & groups[1])

    def test_review_adds_new_jobs_without_erasing_human_decisions(self):
        self.prepare_samples(2)
        self.run_teacher(limit=1)
        scores = self.accept_sheet("run")
        self.run_teacher()
        review(self.root / "run", scores.parent)
        with scores.open(newline="") as stream:
            entries = list(csv.DictReader(stream))
        self.assertEqual(len(entries), 2)
        self.assertEqual(sum(row["decision"] == "accept" for row in entries), 1)

    def test_two_teacher_merge_and_conflicts(self):
        self.prepare_samples(1)
        self.run_teacher("codex", directory="codex")
        self.run_teacher("claude", directory="claude")
        result = merge([self.root / "codex", self.root / "claude"], self.root / "merged")
        self.assertEqual(result, {"samples": 1, "jobs": 2})
        original_saved = next((self.root / "codex").glob("jobs/*/result.json"))
        saved = self.root / "merged" / original_saved.relative_to(self.root / "codex")
        changed = read_json(saved)
        changed["duration_seconds"] = 999
        write_json(saved, changed)
        with self.assertRaisesRegex(ValueError, "Conflicting result"):
            merge([self.root / "codex", self.root / "merged"], self.root / "conflict")
        self.assertFalse((self.root / "conflict").exists())

    def test_archive_extraction_rejects_traversal(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as zipped:
            zipped.writestr("../escape.png", b"bad")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            extract_images(path, self.images)

    def test_invalid_output_remains_for_review_without_automatic_resampling(self):
        self.prepare_samples(1)
        with patch.dict(os.environ, {"GUI_TEST_SCENARIO": "invalid"}):
            self.run_teacher()
        result = self.run_teacher()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(self.counter.read_text(), "1")


if __name__ == "__main__":
    unittest.main()
