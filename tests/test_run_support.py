"""Context snapshots distinguish real changes from tool-generated cache churn."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/harness/scripts"))
from run_support import snapshot_inputs


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        (self.project / "skill/scripts").mkdir(parents=True)
        (self.project / "skill/scripts/helper.py").write_text("pass\n")

    def test_tool_cache_does_not_invalidate_skill_directory(self):
        before = snapshot_inputs(self.project, ["skill"])
        cache = self.project / "skill/scripts/__pycache__"
        cache.mkdir()
        (cache / "helper.cpython-313.pyc").write_bytes(b"generated")
        (self.project / "skill/.pytest_cache").mkdir()
        (self.project / "skill/.pytest_cache/nodeids").write_text("[]")
        self.assertEqual(before, snapshot_inputs(self.project, ["skill"]))

    def test_explicit_cache_input_is_versioned(self):
        cache = self.project / "skill/generated.pyc"
        cache.write_bytes(b"first")
        before = snapshot_inputs(self.project, ["skill/generated.pyc"])
        cache.write_bytes(b"second")
        self.assertNotEqual(before, snapshot_inputs(self.project, ["skill/generated.pyc"]))

    def test_directory_membership_and_code_changes_invalidate_context(self):
        before = snapshot_inputs(self.project, ["skill"])
        source = self.project / "skill/scripts/helper.py"
        source.write_text("print('changed')\n")
        changed = snapshot_inputs(self.project, ["skill"])
        self.assertNotEqual(before, changed)
        source.rename(source.with_name("renamed.py"))
        self.assertNotEqual(changed, snapshot_inputs(self.project, ["skill"]))

    def test_directory_symlink_cycle_is_rejected(self):
        (self.project / "skill/scripts/loop").symlink_to(self.project / "skill", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "cycle"):
            snapshot_inputs(self.project, ["skill"])


if __name__ == "__main__":
    unittest.main()
