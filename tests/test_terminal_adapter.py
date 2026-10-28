"""Terminal boundary tests: profiles must remain addressable after capture."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fontstudio.adapters import TerminalAdapter
from fontstudio.core import History


class TerminalProfileRegression(unittest.TestCase):
    def test_live_tab_size_changes_without_editing_saved_profile(self):
        profiles = {"Basic": {"font": "Menlo-Regular", "size": 12}}
        tabs = {"/dev/ttys000": {"font": "Menlo-Regular", "size": 12},
                    "Pro": {"font": "Monaco", "size": 16}}
        focused = ["Basic"]
        def bridge(operation, *args):
            if operation == "capture":
                return focused[0] + "\nMenlo-Regular\n12\n/dev/ttys000"
            mode, name = args[:2]
            # Reproduce the native failure for IDs that aren't valid profile selectors.
            if mode != "tty":
                raise RuntimeError("Invalid index (-1719)")
            profile = tabs[name]
            if operation == "write":
                profile.update(font=args[2], size=int(args[3]))
            return f"{profile['font']}\n{profile['size']}"
        with tempfile.TemporaryDirectory() as directory, patch(
                "fontstudio.adapters.sys.platform", "darwin"), patch.object(
                TerminalAdapter, "script", side_effect=bridge):
            adapter = TerminalAdapter()
            focused[0] = "Pro"  # A later focus change must not redirect the mutation.
            history = History(Path(directory))
            history.apply(adapter, "Menlo-Italic", 24)
            self.assertEqual(tabs["/dev/ttys000"], {"font": "Menlo-Italic", "size": 24})
            self.assertEqual(profiles["Basic"], {"font": "Menlo-Regular", "size": 12})
            self.assertEqual(tabs["Pro"], {"font": "Monaco", "size": 16})
            self.assertEqual(history.read()[-1]["target"], {"tty": "/dev/ttys000", "profile_name": "Basic"})
            history.undo()
            self.assertEqual(tabs["/dev/ttys000"], {"font": "Menlo-Regular", "size": 12})

    def test_legacy_journal_uses_explicit_id_recovery(self):
        with patch("fontstudio.adapters.sys.platform", "darwin"), patch.object(
                TerminalAdapter, "script", return_value="Menlo-Regular\n12") as bridge:
            adapter = TerminalAdapter("1000")
            self.assertEqual(adapter.read({"target": "1000"}), {"font": "Menlo-Regular", "size": 12})
            bridge.assert_called_once_with("read", "id", "1000")
