"""Real CLI/concurrent-writer checks for explicit communication records."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOGGER = ROOT / "skills/harness/scripts/communication.py"


class CommunicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="harness-communication-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(LOGGER), "--project", str(self.project),
                                 "--run", "test-run", *args], text=True, capture_output=True,
                                timeout=20, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def log(self, body, kind="discovery", **kwargs):
        args = ["log", "--sender", "worker_a", "--recipient", "worker_b", "--kind", kind, "--body", body]
        for key, value in kwargs.items():
            args += ["--" + key.replace("_", "-"), value]
        return json.loads(self.cli(*args).stdout)

    def events(self):
        return [json.loads(line) for line in (self.project / "_workspace/communications/test-run.jsonl").read_text().splitlines()]

    def test_unicode_multiline_message_is_one_jsonl_event(self):
        body = 'API 계약 발견: "profile"\n수정이 필요합니다. 日本語 \\ newline'
        event = self.log(body, task="01")
        self.assertEqual(event["body"], body)
        self.assertEqual(event["delivery"], "recorded")
        self.assertEqual(event["task_id"], "01")
        self.assertEqual(self.events(), [event])
        self.assertFalse((self.project / ".harness").exists())

    def test_answer_and_ack_link_original_message(self):
        question = self.log("Which response field is canonical?", kind="question")
        answer = self.log("Use display_name.", kind="answer", reply_to=question["message_id"], delivery="sent")
        ack = self.log("Contract accepted.", kind="ack", reply_to=answer["message_id"], delivery="received")
        self.assertEqual(ack["reply_to"], answer["message_id"])
        self.assertEqual([e["sequence"] for e in self.events()], [1, 2, 3])

    def test_invalid_reply_does_not_append(self):
        self.log("Before invalid message")
        before = self.events()
        self.cli("log", "--sender", "a", "--recipient", "b", "--kind", "answer",
                 "--body", "Invalid reply", "--reply-to", "does-not-exist", ok=False)
        self.assertEqual(before, self.events())

    def test_answer_requires_correlation(self):
        self.cli("log", "--sender", "a", "--recipient", "b", "--kind", "answer", "--body", "Missing reference", ok=False)
        self.assertFalse((self.project / "_workspace/communications/test-run.jsonl").exists())

    def test_independent_processes_do_not_lose_messages(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            written = list(pool.map(lambda index: self.log(f"Message {index}"), range(24)))
        events = self.events()
        self.assertEqual(len(events), 24)
        self.assertEqual({e["message_id"] for e in events}, {e["message_id"] for e in written})
        self.assertEqual([e["sequence"] for e in events], list(range(1, 25)))
        self.assertEqual({e["body"] for e in events}, {f"Message {i}" for i in range(24)})

    def test_exports_are_separate_and_do_not_change_delivery(self):
        self.log("A discovery", delivery="sent")
        before = self.events()
        output = self.project / "_workspace/communications/test-run.md"
        self.cli("view", "--output", str(output))
        self.assertIn("A discovery", output.read_text())
        self.assertIn("worker_a", output.read_text())
        self.assertEqual(before, self.events())
        self.assertEqual(self.cli("view", "--format", "jsonl").stdout,
                         (self.project / "_workspace/communications/test-run.jsonl").read_text())

    def test_export_cannot_overwrite_log(self):
        self.log("Keep this record")
        before = self.events()
        self.cli("view", "--output", str(self.project / "_workspace/communications/test-run.jsonl"), ok=False)
        self.assertEqual(before, self.events())

    def test_corrupt_tail_is_reported_without_appending(self):
        self.log("Original")
        path = self.project / "_workspace/communications/test-run.jsonl"
        with path.open("a") as stream:
            stream.write('{"broken":')
        before = path.read_bytes()
        self.cli("log", "--sender", "a", "--recipient", "b", "--kind", "progress", "--body", "Later", ok=False)
        self.assertEqual(path.read_bytes(), before)

    def test_body_file_and_delivery_failure(self):
        body = self.project / "message.txt"
        body.write_text("Native transport returned an error.\nNo delivery inferred.")
        event = json.loads(self.cli("log", "--sender", "parent", "--recipient", "child", "--kind", "blocker",
                                   "--body-file", str(body), "--delivery", "failed").stdout)
        self.assertEqual(event["body"], body.read_text())
        self.assertEqual(event["delivery"], "failed")

    def test_destination_symlink_is_rejected(self):
        outside = self.project / "outside"
        outside.mkdir()
        (self.project / "_workspace").symlink_to(outside, target_is_directory=True)
        self.cli("log", "--sender", "a", "--recipient", "b", "--kind", "progress", "--body", "Must not write", ok=False)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
