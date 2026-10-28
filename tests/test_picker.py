"""Exercise the real curses UI and CLI against isolated configuration files."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest


class PickerSmoke(unittest.TestCase):
    def test_apply_undo_and_close_from_real_pty(self):
        self.exercise("xterm-256color", 18, 70)

    def test_monochrome_terminal(self):
        self.exercise("vt100", 24, 80)

    def test_large_terminal_uses_selection_panel(self):
        self.exercise("xterm-256color", 45, 150)

    def exercise(self, term, rows, columns):
        # Font discovery is exercised on the host. No user's terminal settings are changed.
        if sys.platform != "darwin":
            self.skipTest("Host smoke test uses the macOS CoreText font inventory")
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config = temp / "ghostty.conf"
            (temp / "config.json").write_text(json.dumps({
                "terminal": "ghostty", "ghostty_config": str(config)}))
            env = dict(os.environ, TERM=term, HERDR_PLUGIN_CONFIG_DIR=str(temp),
                       HERDR_PLUGIN_STATE_DIR=str(temp / "state"))
            env.pop("SSH_CONNECTION", None)
            env.pop("SSH_TTY", None)
            master, slave = pty.openpty()
            # Approximate the inner popup of a standard 80x24 terminal.
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
            # No subcommand should open the UI directly, without Herdr popup APIs.
            process = subprocess.Popen([sys.executable, "herdr_fonts.py"], cwd=root,
                                       env=env, stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            output = bytearray()
            def until(predicate, seconds=8):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    if predicate():
                        return
                    readable, _, _ = select.select([master], [], [], 0.05)
                    if readable:
                        try:
                            output.extend(os.read(master, 65536))
                        except OSError:
                            break
                self.fail(output.decode(errors="replace")[-2000:])
            try:
                until(lambda: b"HERDR FONTS" in output)
                self.assertNotIn(b"needs at least", output)
                self.assertNotIn(b"macOS Terminal", output)
                self.assertNotIn(b"Turkce", output)
                self.assertIn(b"Control+S", output)
                if columns >= 110:
                    self.assertIn(b"SELECTED FONT", output)
                os.write(master, b"\x14")
                until(lambda: b"Choose your terminal" in output)
                os.write(master, b"\n")
                os.write(master, b"\x13")
                until(lambda: b"Enter save / Esc cancel" in output)
                os.write(master, b"25\x1b")  # Cancel size editing, not the popup.
                output.clear()
                os.write(master, b"\x13")
                until(lambda: b"Enter save / Esc cancel" in output)
                os.write(master, b"16.5\n")
                output.clear()
                until(lambda: b"6.5 pt" in output)
                os.write(master, b"\x1bOC")  # Right arrow increments the size, without Shift/+.
                os.write(master, b"Monaco")
                until(lambda: b"Monaco" in output)
                os.write(master, b"\n")
                until(lambda: config.exists())
                self.assertIn("# BEGIN HERDR FONT STUDIO", config.read_text())
                self.assertIn("font-size = 17.5", config.read_text())
                self.assertIn('font-family = "Monaco"', config.read_text())
                os.write(master, b"\x15")
                until(lambda: not config.exists())
                os.write(master, b"\x1b")
                until(lambda: process.poll() is not None)
                process.wait(timeout=5)
                self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
                self.assertEqual(json.loads((temp / "state/history.json").read_text()), [])
                remembered = json.loads((temp / "config.json").read_text())
                self.assertEqual(remembered["terminal"], "ghostty")
                self.assertEqual(remembered["font"], "Monaco")
                self.assertEqual(remembered["size"], 17.5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)


if __name__ == "__main__":
    unittest.main()
