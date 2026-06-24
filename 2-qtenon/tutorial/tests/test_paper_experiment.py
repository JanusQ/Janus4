"""Tests for the VQE/SPSA paper-figure reproduction helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tutorial.helpers.common import TutorialPaths
from tutorial.helpers.local_run import CompileResult, LocalRunResult
from tutorial.helpers.paper_experiment import (
    PAPER_VQE_MAX_CYCLES,
    PAPER_VQE_SOURCE,
    PaperExperimentParseError,
    derive_vqe_spsa_time_breakdown,
    paper_breakdown_plot_rows,
    paper_breakdown_table_rows,
    parse_paper_vqe_log,
    run_paper_vqe_spsa,
)


SAMPLE_LOG = """\
[UART] UART0 is here (stdin/stdout).
paper_vqe_spsa,v3
metric,qubits,64
metric,shots,500
metric,iterations,10
metric,parameters,256
metric,q_set_calls,64
metric,q_update_calls,5376
metric,q_gen_calls,20
metric,q_run_calls,20
metric,total_cycles,123456
metric,qtenon_host_cycles_rdcycle,1338502
metric,qtenon_schedule_removed_cycles_rdcycle,3356063
metric,qtenon_without_software_host_cycles_rdcycle,4694565
metric,qtenon_host_target_cycles,1338502
metric,qtenon_schedule_removed_target_cycles,3356063
paper_vqe_spsa,done
"""


class PaperExperimentParserTest(unittest.TestCase):
    def test_parse_paper_vqe_log_recovers_metrics_and_derives_breakdown(self) -> None:
        parsed = parse_paper_vqe_log(SAMPLE_LOG)

        self.assertEqual(parsed.metric("qubits"), 64)
        self.assertEqual(parsed.metric("shots"), 500)
        rows = derive_vqe_spsa_time_breakdown(parsed)
        self.assertEqual(len(rows), 12)

        baseline_rows = parsed.breakdown_for("baseline")
        self.assertEqual([row.component for row in baseline_rows][0], "quantum_execution")
        self.assertAlmostEqual(baseline_rows[0].total_ms, 204.3)
        self.assertAlmostEqual(baseline_rows[0].component_percent, 7.861, places=3)
        self.assertAlmostEqual(baseline_rows[0].component_ms, 16.06002)
        qtenon_rows = parsed.breakdown_for("qtenon")
        self.assertAlmostEqual(qtenon_rows[-1].component_ms, 1.338502)
        self.assertEqual(qtenon_rows[-1].source, "verilator_rdcycle")

    def test_parse_paper_vqe_log_requires_rows(self) -> None:
        with self.assertRaises(PaperExperimentParseError):
            parse_paper_vqe_log("metric,qubits,64\n")
        with self.assertRaises(PaperExperimentParseError):
            parse_paper_vqe_log("paper_vqe_spsa,done\n")
        with self.assertRaises(PaperExperimentParseError):
            parse_paper_vqe_log(SAMPLE_LOG.replace("metric,qtenon_host_cycles_rdcycle,1338502\n", ""))

    def test_plot_and_table_rows_use_paper_order(self) -> None:
        parsed = parse_paper_vqe_log(SAMPLE_LOG)
        plot_rows = paper_breakdown_plot_rows(parsed)
        table_rows = paper_breakdown_table_rows(parsed)

        self.assertEqual(list(plot_rows), ["baseline", "qtenon_without_software", "qtenon"])
        self.assertEqual([row.component for row in plot_rows["qtenon"]], [
            "quantum_execution",
            "quantum_host_comm",
            "pulse_generation",
            "host_computation",
        ])
        self.assertEqual(table_rows[0][0], "Baseline")
        self.assertEqual(table_rows[-1][0], "Qtenon")
        self.assertAlmostEqual(plot_rows["qtenon"][0].total_ms, 18.071253)
        self.assertEqual(plot_rows["qtenon"][0].source, "paper_quantum_model")


class PaperExperimentRunnerTest(unittest.TestCase):
    def test_run_paper_vqe_spsa_live_uses_existing_local_run_helpers(self) -> None:
        paths = TutorialPaths.discover(Path(__file__))
        with tempfile.TemporaryDirectory() as tmp_str:
            run_dir = Path(tmp_str)
            simulator = run_dir / "simulator-chipyard.harness-QChipRocketConfig"
            trace_path = run_dir / "paper_vqe_spsa.trace.txt"
            log_path = run_dir / "paper_vqe_spsa.log"

            def fake_compile(src: Path, elf: Path) -> CompileResult:
                self.assertEqual(src, paths.tests_dir / PAPER_VQE_SOURCE)
                elf.parent.mkdir(parents=True, exist_ok=True)
                elf.write_bytes(b"\x7fELF")
                elf.with_suffix(elf.suffix + ".objdump.txt").write_text(
                    "paper_vqe_spsa.elf: file format elf64-littleriscv\n",
                    encoding="utf-8",
                )
                return CompileResult(elf_path=elf, elf_bytes=4, wall_seconds=0.1)

            def fake_run(*args, **kwargs) -> LocalRunResult:  # type: ignore[no-untyped-def]
                trace_path.write_text("- Verilog $finish\n", encoding="utf-8")
                log_path.write_text(SAMPLE_LOG, encoding="utf-8")
                return LocalRunResult(
                    trace_path=trace_path,
                    log_path=log_path,
                    trace_bytes=trace_path.stat().st_size,
                    log_bytes=log_path.stat().st_size,
                    cycle_count=42,
                    custom0_count=3,
                    wall_seconds=0.2,
                )

            with mock.patch(
                "tutorial.helpers.paper_experiment.ensure_simulator",
                return_value=simulator,
            ) as ensure_mock, mock.patch(
                "tutorial.helpers.paper_experiment.compile_elf",
                side_effect=fake_compile,
            ) as compile_mock, mock.patch(
                "tutorial.helpers.paper_experiment.run_local_sim",
                side_effect=fake_run,
            ) as run_mock:
                artifacts = run_paper_vqe_spsa(paths, run_dir, live=True)

        ensure_mock.assert_called_once_with(paths.chipyard_root, paths.config_name)
        compile_mock.assert_called_once()
        run_mock.assert_called_once()
        self.assertTrue(run_mock.call_args.kwargs["fast"])
        self.assertEqual(
            run_mock.call_args.kwargs["sim_flags"],
            [f"+max-cycles={PAPER_VQE_MAX_CYCLES}"],
        )
        self.assertEqual(artifacts.source, "live")
        self.assertIsNotNone(artifacts.parsed)
        assert artifacts.parsed is not None
        self.assertEqual(artifacts.parsed.metric("total_cycles"), 123456)


if __name__ == "__main__":
    unittest.main()
