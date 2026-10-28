import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fontstudio.adapters import detect, current_terminal
from fontstudio.core import StudioError
from fontstudio.shortcut import install
from fontstudio.launcher import install as install_launcher


class Detection(unittest.TestCase):
    def test_control_labels_follow_platform(self):
        from fontstudio.ui import control_label
        self.assertEqual(control_label("darwin"), "Control")
        self.assertEqual(control_label("linux"), "Ctrl")
    def test_current_terminal_wins_over_stale_saved_preference(self):
        with patch.dict(os.environ, {"TERM_PROGRAM": "ghostty"}, clear=True):
            self.assertEqual(current_terminal({"terminal": "terminal"}), "ghostty")

    def test_saved_terminal_only_used_when_detection_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(current_terminal({"terminal": "terminal"}), "terminal")
    def test_detects_outer_terminal_inside_tmux(self):
        with patch.dict(os.environ, {"TERM_PROGRAM": "Apple_Terminal", "TERM": "screen-256color"}, clear=True):
            self.assertEqual(detect(), "terminal")

    def test_does_not_guess_ghostty_for_unknown_terminal(self):
        with patch.dict(os.environ, {"TERM": "screen-256color"}, clear=True):
            self.assertIsNone(detect())

    def test_recognizes_known_terminal_signals(self):
        for env, expected in [({"TERM_PROGRAM": "ghostty"}, "ghostty"),
                              ({"TERM_PROGRAM": "iTerm.app"}, "iterm2"),
                              ({"KITTY_WINDOW_ID": "3"}, "kitty"),
                              ({"TERM": "xterm-ghostty"}, "ghostty")]:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                self.assertEqual(detect(), expected)


class Shortcut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "config.toml"

    def test_install_preserves_config_and_backup(self):
        original = '[theme]\nname = "nord"\n'
        self.path.write_text(original)
        install(self.path)
        self.assertTrue(self.path.read_text().startswith(original))
        self.assertEqual(self.path.with_name("config.toml.font-studio.bak").read_text(), original)
        self.assertIn('key = "prefix+f"', self.path.read_text())
        self.assertIn('command = "herdr.fonts.open"', self.path.read_text())

    def test_install_is_idempotent(self):
        install(self.path)
        first = self.path.read_bytes()
        install(self.path)
        self.assertEqual(self.path.read_bytes(), first)

    def test_existing_other_shortcut_is_respected(self):
        self.path.write_text('[[keys.command]]\nkey = "prefix+j"\ncommand = "herdr.fonts.open"\n')
        self.assertIn("prefix+j", install(self.path))
        self.assertNotIn("prefix+f", self.path.read_text())

    def test_conflicting_key_is_not_overwritten(self):
        original = '[[keys.command]]\nkey = "prefix+f"\ncommand = "other.action"\n'
        self.path.write_text(original)
        with self.assertRaises(StudioError):
            install(self.path)
        self.assertEqual(self.path.read_text(), original)


class Launcher(unittest.TestCase):
    def test_installed_command_can_launch_from_another_directory(self):
        import subprocess
        with tempfile.TemporaryDirectory(prefix="font studio ") as directory:
            install_launcher(directory)
            command = Path(directory) / "herdr-fonts"
            result = subprocess.run([str(command), "--help"], cwd="/tmp", capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("picker", result.stdout)

    def test_does_not_replace_unrelated_command(self):
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "herdr-fonts"
            command.write_text("existing command")
            with self.assertRaises(StudioError):
                install_launcher(directory)
            self.assertEqual(command.read_text(), "existing command")
