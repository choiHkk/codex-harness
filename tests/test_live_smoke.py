"""Offline checks for live-test evidence; these do not simulate native agents."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import live_smoke


class LiveEvidenceTests(unittest.TestCase):
    def test_installed_checker_change_is_rejected_before_verification_imports(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve() / "fixture"
            live_smoke.prepare(project)
            baseline = live_smoke.protected_hashes(project)
            helper = project / ".agents/skills/harness/scripts/run_checks.py"
            helper.write_text("raise RuntimeError('Do not import changed helper')\n")
            with self.assertRaisesRegex(ValueError, "Protected fixture files changed"):
                live_smoke.verify(project, baseline)

    def test_unrelated_delivery_does_not_prove_question_and_answer_delivery(self):
        question = {"message_id": "q", "kind": "question", "sender": "alpha", "recipient": "beta", "delivery": "recorded"}
        answer = {"message_id": "a", "reply_to": "q", "kind": "answer", "sender": "beta", "recipient": "alpha", "delivery": "recorded"}
        progress = {"message_id": "p", "kind": "progress", "sender": "alpha", "recipient": "parent", "delivery": "sent"}
        self.assertEqual(live_smoke.peer_answers([question, answer, progress], {"alpha", "beta"}), [])
        receipts = [{"message_id": "rq", "reply_to": "q", "kind": "ack", "delivery": "received"},
                    {"message_id": "ra", "reply_to": "a", "kind": "ack", "delivery": "sent"}]
        self.assertEqual(live_smoke.peer_answers([question, answer, *receipts], {"alpha", "beta"}), [answer])

    def test_correlated_answer_must_come_from_the_addressed_peer(self):
        question = {"message_id": "q", "kind": "question", "sender": "alpha", "recipient": "beta", "delivery": "sent"}
        answer = {"message_id": "a", "reply_to": "q", "kind": "answer", "sender": "someone-else", "recipient": "alpha", "delivery": "received"}
        self.assertEqual(live_smoke.peer_answers([question, answer], {"alpha", "beta"}), [])


if __name__ == "__main__":
    unittest.main()
