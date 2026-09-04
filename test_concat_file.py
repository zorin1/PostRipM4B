#!/usr/bin/env python3
"""
Unit tests for AudioBookConverter._create_concat_file

Verifies that paths containing single quotes (apostrophes) are escaped
correctly for the ffmpeg concat demuxer. Without escaping, ffmpeg truncates
the path at the apostrophe (e.g. "...Dragon's Tail" -> "...Dragon")
and fails with "Impossible to open" / "No such file or directory".

Run:  python3 -m pytest test_concat_file.py -v
  or  python3 test_concat_file.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from PostRipM4B import AudioBookConverter, Config, Verbosity


# Book folder names that previously broke the concat demuxer
TRICKY_BOOK_FOLDERS = [
    "G. Z. Zzz - The Snoozing Dragon's Tail",
    "The Dragon's Hoard's Keeper's Key",
]


def make_converter(temp_dir: str) -> AudioBookConverter:
    """Build an AudioBookConverter without needing real ffmpeg/ffprobe."""
    config = Config()
    config.input_dir = temp_dir
    config.temp_dir = temp_dir
    config.verbosity = Verbosity.QUIET
    config.ffmpeg_path = "ffmpeg"
    config.ffprobe_path = "ffprobe"
    return AudioBookConverter(config)


def ffmpeg_concat_unquote(line: str) -> str:
    """
    Parse one line from a concat list the same way the ffmpeg concat
    demuxer does: text after "file " up to EOL, unquoting single-quoted
    strings in which a literal quote is written as '\\''.
    """
    line = line.strip()
    if not line.startswith("file "):
        raise ValueError(f"Not a file directive: {line!r}")
    rest = line[len("file "):].strip()

    result = []
    i = 0
    in_quotes = False
    while i < len(rest):
        ch = rest[i]
        if ch == "'":
            if in_quotes:
                # The '\'' idiom: close quote, escaped literal quote, reopen
                if rest.startswith("'\\''", i):
                    result.append("'")
                    i += 4
                    continue
                in_quotes = False
            else:
                in_quotes = True
            i += 1
        elif ch == "\\" and not in_quotes and i + 1 < len(rest):
            result.append(rest[i + 1])
            i += 2
        else:
            result.append(ch)
            i += 1
    return "".join(result)


class TestConcatFileEscaping(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="postrip_test_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_plain_path_round_trips(self):
        book_dir = os.path.join(self.tmp, "Mick Herron - Real Tigers")
        os.makedirs(book_dir)
        m4b = os.path.join(book_dir, "part1.m4b")
        Path(m4b).touch()

        converter = make_converter(self.tmp)
        converter.intermediate_files = [m4b]

        concat_file = converter._create_concat_file()
        with open(concat_file) as f:
            lines = f.read().splitlines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(ffmpeg_concat_unquote(lines[0]), os.path.abspath(m4b))

    def test_apostrophe_in_path_round_trips(self):
        for folder in TRICKY_BOOK_FOLDERS:
            with self.subTest(folder=folder):
                book_dir = os.path.join(self.tmp, folder)
                os.makedirs(book_dir, exist_ok=True)
                m4b = os.path.join(book_dir, "part1.m4b")
                Path(m4b).touch()

                converter = make_converter(self.tmp)
                converter.intermediate_files = [m4b]

                concat_file = converter._create_concat_file()
                with open(concat_file) as f:
                    lines = f.read().splitlines()

                # Path must survive ffmpeg's unquoting intact
                self.assertEqual(
                    ffmpeg_concat_unquote(lines[0]),
                    os.path.abspath(m4b),
                )
                # Inner path must contain only escaped apostrophes
                raw = lines[0]
                self.assertTrue(raw.startswith("file '") and raw.endswith("'"))
                inner = raw[len("file '"):-1].replace("'\\''", "")
                self.assertNotIn("'", inner)

    def test_multiple_files_with_apostrophes(self):
        folder = os.path.join(self.tmp, TRICKY_BOOK_FOLDERS[0])
        os.makedirs(folder)
        m4bs = [os.path.join(folder, f"part{i}.m4b") for i in range(1, 4)]
        for m4b in m4bs:
            Path(m4b).touch()

        converter = make_converter(self.tmp)
        converter.intermediate_files = m4bs

        concat_file = converter._create_concat_file()
        with open(concat_file) as f:
            lines = f.read().splitlines()

        self.assertEqual(len(lines), len(m4bs))
        for line, m4b in zip(lines, m4bs):
            self.assertEqual(ffmpeg_concat_unquote(line), os.path.abspath(m4b))


@unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg not installed")
class TestConcatFileWithRealFfmpeg(unittest.TestCase):
    """End-to-end: real ffmpeg must accept the generated concat list."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="postrip_ffmpeg_test_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_ffmpeg_accepts_concat_list_with_apostrophes(self):
        folder = os.path.join(self.tmp, TRICKY_BOOK_FOLDERS[0])
        os.makedirs(folder)
        m4b = os.path.join(folder, "part1.m4b")
        # Generate a real (tiny) m4a so ffmpeg can fully parse it
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2",
             "-c:a", "aac", "-y", m4b],
            capture_output=True, text=True, check=True,
        )

        converter = make_converter(self.tmp)
        converter.intermediate_files = [m4b]
        concat_file = converter._create_concat_file()

        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "concat", "-safe", "0",
             "-i", concat_file, "-f", "null", "-"],
            capture_output=True, text=True,
        )
        # Exit code 0 means every listed input was opened successfully.
        # Before the fix this failed with "Impossible to open '...Dragon'".
        self.assertEqual(
            result.returncode, 0,
            f"ffmpeg rejected concat list:\n{result.stderr}",
        )
        self.assertNotIn("Impossible to open", result.stderr)
        self.assertNotIn("No such file", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
