"""Unit tests for the presentation helpers in :mod:`tutorial.helpers.notebook_support`.

Live-run tests live in :mod:`tutorial.tests.test_local_run`; archive-reader
tests live in :mod:`tutorial.tests.test_archive`. This module covers what
remains in ``notebook_support.py`` after the Scope 3 split:

- ``format_table``
- ``parse_hybrid_output``
- ``parse_objdump_custom_commands``
- the three inline-SVG helpers
- the re-export wiring back to ``local_run`` / ``archive``.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tutorial.helpers.archive import load_capture_static
from tutorial.helpers.common import TutorialPaths
from tutorial.helpers.notebook_support import (
    IterationTransfer,
    ScaleBar,
    SwimlaneSegment,
    assert_clean_finish,
    bytes_per_iter_bar,
    format_table,
    parse_hybrid_output,
    parse_objdump_custom_commands,
    path_latency_bar,
    swimlane_plot,
)


class NotebookSupportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.paths = TutorialPaths.discover(Path(__file__))

    def test_format_table_aligns_rows(self) -> None:
        rendered = format_table(["name", "value"], [["theta0", 12], ["theta1", 38]])
        self.assertIn("name", rendered)
        self.assertIn("theta1", rendered)
        self.assertIn("-+-", rendered)

    def test_assert_clean_finish_accepts_finish_marker(self) -> None:
        capture = load_capture_static(self.paths.captures_dir, "hybrid_loop")
        self.assertIn("Verilog $finish", capture.log_text)
        # Should not raise on the checked-in archive.
        assert_clean_finish(capture.log_text)

    def test_assert_clean_finish_rejects_truncated_log(self) -> None:
        with self.assertRaises(AssertionError):
            assert_clean_finish("simulator crashed before $finish\n")

    def test_parse_hybrid_output_ignores_simulator_noise(self) -> None:
        capture = load_capture_static(self.paths.captures_dir, "hybrid_loop")
        rows = parse_hybrid_output(capture.log_text)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0].sample_bits, "01")
        self.assertEqual(rows[-1].acquire_word_hex, "0x40f00ab900370026")

    def test_parse_objdump_custom_commands_recovers_qtenon_commands(self) -> None:
        capture = load_capture_static(self.paths.captures_dir, "hybrid_loop")
        commands = parse_objdump_custom_commands(capture.objdump_text)
        self.assertEqual(commands[0].command, "q_update")
        self.assertEqual(commands[-1].command, "q_set")

    def test_svg_helpers_return_inline_svg(self) -> None:
        latency_svg = path_latency_bar(
            [
                ScaleBar("Decoupled", 1_000_000.0, "paper-scale baseline", "#dc2626"),
                ScaleBar("Path ②", 50.0, "bulk on-chip", "#f59e0b"),
                ScaleBar("Path ①", 1.0, "register update", "#0f766e"),
            ]
        )
        bytes_svg = bytes_per_iter_bar(
            [
                IterationTransfer("iter 0", 0.0, 264.0),
                IterationTransfer("iter 1", 8.0, 8.0),
            ]
        )
        swimlane_svg = swimlane_plot(
            [
                SwimlaneSegment("Host", 0.0, 10.0, "post-process", "#dbeafe"),
                SwimlaneSegment("Controller", 10.0, 40.0, "q_run", "#fde68a"),
            ]
        )
        self.assertIn("<svg", latency_svg)
        self.assertIn("Bytes moved per iteration", bytes_svg)
        self.assertIn("Schematic host/controller swimlane", swimlane_svg)


class BackwardCompatReExportTest(unittest.TestCase):
    """The notebook template imports everything through notebook_support.

    This regression guards the PRD's scope-3 constraint: build_notebook.py
    should keep working without touching cell imports after the split.
    """

    def test_notebook_support_re_exports_local_run_and_archive_symbols(
        self,
    ) -> None:
        from tutorial.helpers.notebook_support import (
            CaptureMissing,
            CompileResult,
            DEFAULT_TIMING_ASSUMPTIONS,
            LiveRun,
            LocalRunResult,
            ObjdumpLine,
            PaperExperimentLog,
            StaticCapture,
            ToolchainMissing,
            VerilatorMissing,
            compile_elf,
            ensure_simulator,
            find_objdump_line,
            load_capture_static,
            parse_paper_vqe_log,
            run_local_sim,
            run_paper_vqe_spsa,
            source_block,
        )

        # Spot-check that the re-exports are the genuine article rather
        # than lookalikes with the same name.
        from tutorial.helpers import archive as _archive
        from tutorial.helpers import local_run as _local_run
        from tutorial.helpers import paper_experiment as _paper_experiment

        self.assertIs(CaptureMissing, _archive.CaptureMissing)
        self.assertIs(StaticCapture, _archive.StaticCapture)
        self.assertIs(ObjdumpLine, _archive.ObjdumpLine)
        self.assertIs(load_capture_static, _archive.load_capture_static)
        self.assertIs(source_block, _archive.source_block)
        self.assertIs(find_objdump_line, _archive.find_objdump_line)

        self.assertIs(CompileResult, _local_run.CompileResult)
        self.assertIs(LocalRunResult, _local_run.LocalRunResult)
        self.assertIs(LiveRun, _local_run.LiveRun)
        self.assertIs(ToolchainMissing, _local_run.ToolchainMissing)
        self.assertIs(VerilatorMissing, _local_run.VerilatorMissing)
        self.assertIs(compile_elf, _local_run.compile_elf)
        self.assertIs(ensure_simulator, _local_run.ensure_simulator)
        self.assertIs(run_local_sim, _local_run.run_local_sim)
        self.assertIs(PaperExperimentLog, _paper_experiment.PaperExperimentLog)
        self.assertIs(DEFAULT_TIMING_ASSUMPTIONS, _paper_experiment.DEFAULT_TIMING_ASSUMPTIONS)
        self.assertIs(parse_paper_vqe_log, _paper_experiment.parse_paper_vqe_log)
        self.assertIs(run_paper_vqe_spsa, _paper_experiment.run_paper_vqe_spsa)


if __name__ == "__main__":
    unittest.main()
