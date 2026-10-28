import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fontstudio.adapters import ConfigAdapter, managed_config, create, config_path, TerminalAdapter
from fontstudio.core import History, StudioError, validate_size
from fontstudio.fonts import Font


class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.history = History(self.root / "state")
        self.path = self.root / "config"
        self.adapter = ConfigAdapter("ghostty", self.path)
        self.faces = patch("fontstudio.fonts.installed", return_value=[Font("Test Mono", "TestMono-Regular")])
        self.faces.start()
        self.addCleanup(self.faces.stop)

    def apply(self, size=14):
        return self.history.apply(self.adapter, "TestMono-Regular", size)

    def test_apply_and_undo_preserve_original_bytes(self):
        original = b"# existing\r\nfont-family = Old\r\nbackground = #123456"
        self.path.write_bytes(original)
        self.apply()
        text = self.path.read_text()
        self.assertIn('font-family = "Test Mono"', text)
        self.history.undo()
        self.assertEqual(self.path.read_bytes(), original)

    def test_new_config_is_removed_on_undo(self):
        self.apply()
        self.history.undo()
        self.assertFalse(self.path.exists())

    def test_external_edits_are_preserved(self):
        self.apply()
        self.path.write_text(self.path.read_text() + "# external\n")
        with self.assertRaisesRegex(StudioError, "outside"):
            self.history.undo()
        self.assertIn("# external", self.path.read_text())

    def test_multiple_changes_unwind_in_order(self):
        self.apply(12)
        first = self.path.read_bytes()
        self.apply(18)
        self.assertEqual(self.path.read_text().count("# BEGIN"), 1)
        self.history.undo()
        self.assertEqual(self.path.read_bytes(), first)
        self.history.undo()
        self.assertFalse(self.path.exists())

    def test_write_ahead_survives_failure_after_write(self):
        write = self.adapter.write
        def interrupted(change, value):
            write(change, value)
            raise OSError("interrupted")
        with patch.object(self.adapter, "write", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.apply()
        self.assertTrue(self.history.read()[-1]["pending"])
        with self.assertRaisesRegex(StudioError, "recovery"):
            self.apply()
        self.history.undo()
        self.assertFalse(self.path.exists())

    def test_silent_failed_write_never_reports_success(self):
        with patch.object(self.adapter, "write", return_value=None):
            with self.assertRaisesRegex(StudioError, "did not confirm"):
                self.apply()
        self.assertTrue(self.history.read()[-1]["pending"])
        self.history.undo()
        self.assertEqual(self.history.read(), [])

    def test_undo_failed_write_that_changed_nothing(self):
        with patch.object(self.adapter, "write", side_effect=OSError("failed")):
            with self.assertRaises(OSError):
                self.apply()
        self.history.undo()
        self.assertEqual(self.history.read(), [])

    def test_symlink_preserved(self):
        target = self.root / "real-config"
        target.write_text("# original")
        self.path.symlink_to(target)
        adapter = ConfigAdapter("kitty", self.path)
        self.history.apply(adapter, "TestMono-Regular", 12)
        self.assertTrue(self.path.is_symlink())
        self.assertIn('postscript_name="TestMono-Regular"', target.read_text())
        self.history.undo()
        self.assertEqual(target.read_text(), "# original")

    def test_invalid_sizes(self):
        for size in (float("nan"), float("inf"), 0, 100, "bad"):
            with self.assertRaises(StudioError):
                validate_size(size)

    def test_malformed_markers_do_not_overwrite_config(self):
        self.path.write_text("# BEGIN HERDR FONT STUDIO\n")
        with self.assertRaises(StudioError):
            self.apply()
        self.assertEqual(self.history.read(), [])

    def test_malformed_history_does_not_get_overwritten(self):
        self.history.root.mkdir()
        self.history.path.write_text("not json")
        with self.assertRaises(StudioError):
            self.apply()
        self.assertFalse(self.path.exists())

    def test_reject_unknown_font_without_mutation(self):
        with self.assertRaises(StudioError):
            self.history.apply(self.adapter, "MissingFont", 14)
        self.assertFalse(self.path.exists())

    def test_apply_moves_managed_block_after_external_font_overrides(self):
        self.apply()
        self.path.write_text(self.path.read_text() + "font-size = 30\n")
        self.apply(18)
        text = self.path.read_text()
        self.assertLess(text.index("font-size = 30"), text.index("# BEGIN"))
        self.assertEqual(text.count("# BEGIN"), 1)
        self.assertTrue(text.endswith("font-size = 18\n# END HERDR FONT STUDIO\n"))

    def test_remote_session_rejected(self):
        with patch.dict("os.environ", {"SSH_CONNECTION": "remote"}):
            with self.assertRaisesRegex(StudioError, "local"):
                create("kitty")

    def test_ambiguous_ghostty_config_requires_explicit_path(self):
        with patch("fontstudio.adapters.Path.home", return_value=self.root), patch.dict(
                "os.environ", {"XDG_CONFIG_HOME": str(self.root / ".config")}):
            for path in (self.root / ".config/ghostty/config", self.root / "Library/Application Support/com.mitchellh.ghostty/config"):
                path.parent.mkdir(parents=True)
                path.touch()
            with patch("fontstudio.adapters.sys.platform", "darwin"):
                with self.assertRaisesRegex(StudioError, "Multiple"):
                    config_path("ghostty", {})

    def test_terminal_partial_failure_can_be_recovered(self):
        change = {"terminal": "terminal", "target": "7", "pending": True,
                  "before": {"font": "Old", "size": 12}, "after": {"font": "New", "size": 18}}
        self.history.root.mkdir()
        self.history.save([change])
        adapter = unittest.mock.Mock()
        adapter.read.return_value = {"font": "New", "size": 12}
        adapter.message = "Restored"
        with patch("fontstudio.adapters.adapter_for_change", return_value=adapter):
            self.history.undo()
        adapter.write.assert_called_once_with(change, change["before"])


if __name__ == "__main__":
    unittest.main()
