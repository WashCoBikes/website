"""Regression tests for the read-only Markdown image checker."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).with_name("check-alt-text.py")


class AltTextTests(unittest.TestCase):
    def run_check(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "about.md"
            path.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CHECKER), "--content", directory],
                capture_output=True, text=True,
            )
            self.assertEqual(path.read_text(encoding="utf-8"), text)
            return result

    def test_former_mapping_entry_still_fails_when_empty(self):
        result = self.run_check("# About\n\n![](../../assets/images/Headshot1-NB-1x1_200.jpg)\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("about.md:3", result.stderr)

    def test_whitespace_and_reference_images_fail(self):
        for image in ["![  ](photo.jpg)", "![][photo]\n\n[photo]: photo.jpg"]:
            with self.subTest(image=image):
                self.assertEqual(self.run_check(image).returncode, 1)

    def test_described_images_pass(self):
        result = self.run_check("![Riders](photo_(2).jpg)\n![Riders][photo]\n\n[photo]: photo.jpg\n")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
