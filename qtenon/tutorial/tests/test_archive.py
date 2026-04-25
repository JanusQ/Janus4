"""Unit tests for :mod:`tutorial.helpers.archive` checked-in replay reader."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tutorial.helpers.archive import (
    CaptureMissing,
    ObjdumpLine,
    StaticCapture,
    find_objdump_line,
    load_capture_static,
    source_block,
)
from tutorial.helpers.common import TutorialPaths
from tutorial.helpers.trace import parse_trace_text


class ArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.paths = TutorialPaths.discover(Path(__file__))

    def test_load_capture_static_reads_three_archive_files(self) -> None:
        capture = load_capture_static(self.paths.captures_dir, "hybrid_loop")
        self.assertIsInstance(capture, StaticCapture)
        for path in (capture.trace_path, capture.objdump_path, capture.log_path):
            self.assertTrue(path.is_file(), f"{path} should exist")
        self.assertTrue(capture.trace_text)
        self.assertTrue(capture.objdump_text)
        self.assertTrue(capture.log_text)

    def test_load_capture_static_raises_for_missing_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CaptureMissing):
                load_capture_static(Path(tmp), "nonexistent")

    def test_load_capture_static_raises_when_archive_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            capture_dir = tmp / "hybrid_loop"
            capture_dir.mkdir()
            # Create only one of the required files — trace.txt.
            (capture_dir / "hybrid_loop.trace.txt").write_text("stub", encoding="utf-8")
            with self.assertRaises(CaptureMissing):
                load_capture_static(tmp, "hybrid_loop")

    def test_source_block_extracts_inclusive_macro_body(self) -> None:
        rocc_h = self.paths.tests_dir / "rocc.h"
        block = source_block(rocc_h, "#define q_set", "}")
        lines = block.splitlines()
        self.assertGreaterEqual(len(lines), 3)
        self.assertTrue(lines[0].lstrip().startswith("#define q_set"))
        self.assertIn("}", lines[-1])
        self.assertTrue(any(".insn r" in line for line in lines))

    def test_source_block_raises_when_markers_missing(self) -> None:
        rocc_h = self.paths.tests_dir / "rocc.h"
        with self.assertRaises(ValueError):
            source_block(rocc_h, "#define q_does_not_exist", "}")

    def test_find_objdump_line_locates_first_q_set_from_trace(self) -> None:
        capture = load_capture_static(self.paths.captures_dir, "hybrid_loop")
        parsed = parse_trace_text(capture.trace_text)
        first_q_set = next(entry for entry in parsed if entry.command == "q_set")
        self.assertIsNotNone(first_q_set.pc)
        assert first_q_set.pc is not None  # narrow for type-checker
        hit = find_objdump_line(
            capture.objdump_text,
            first_q_set.pc,
            first_q_set.instruction,
        )
        self.assertIsInstance(hit, ObjdumpLine)
        self.assertEqual(int(hit.pc_hex, 16), first_q_set.pc)
        self.assertEqual(int(hit.hex_word, 16), first_q_set.instruction)
        self.assertIn(".4byte", hit.raw_line)

    def test_find_objdump_line_raises_when_word_mismatch(self) -> None:
        capture = load_capture_static(self.paths.captures_dir, "hybrid_loop")
        parsed = parse_trace_text(capture.trace_text)
        first_q_set = next(entry for entry in parsed if entry.command == "q_set")
        assert first_q_set.pc is not None
        with self.assertRaises(ValueError):
            find_objdump_line(
                capture.objdump_text,
                first_q_set.pc,
                0xDEADBEEF,
            )


if __name__ == "__main__":
    unittest.main()
