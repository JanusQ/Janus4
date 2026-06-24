"""Paper-experiment runner and parser helpers for the Qtenon tutorial.

This module owns the VQE/SPSA reproduction lane used by the notebook's
paper-figure section:

- optional live compile/run through ``QChipRocketConfig``
- replay of checked-in capture artifacts
- parsing the machine-readable ``metric,`` log rows
- deriving the paper ``time_breakdown`` rows from those metrics plus the
  evaluation assumptions documented in paper Section 7 and the archived eval
  scripts

The helper keeps the notebook thin and gives the tests a single place to
exercise the command construction and parsing boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import re

from .archive import StaticCapture, load_capture_static
from .common import TutorialPaths
from .local_run import (
    CompileResult,
    LiveRun,
    LocalRunResult,
    compile_elf,
    ensure_simulator,
    run_local_sim,
)

PAPER_VQE_BENCHMARK = "paper_vqe_spsa"
PAPER_VQE_SOURCE = "paper_vqe_spsa.c"
PAPER_VQE_CAPTURE = "paper_vqe_spsa"
PAPER_VQE_MAX_CYCLES = 30_000_000
TARGET_CORE_GHZ = 1.0
TARGET_CYCLE_NS = 1.0 / TARGET_CORE_GHZ

SCENARIO_ORDER = ("baseline", "qtenon_without_software", "qtenon")
COMPONENT_ORDER = (
    "quantum_execution",
    "quantum_host_comm",
    "pulse_generation",
    "host_computation",
)

SCENARIO_LABELS = {
    "baseline": "Baseline",
    "qtenon_without_software": "Qtenon w/o software",
    "qtenon": "Qtenon",
}

COMPONENT_LABELS = {
    "quantum_execution": "Quantum execution",
    "quantum_host_comm": "Quantum-host comm.",
    "pulse_generation": "Pulse generation",
    "host_computation": "Host computation",
}


class PaperExperimentParseError(ValueError):
    """Raised when a paper benchmark log lacks the expected machine-readable rows."""


@dataclass(frozen=True)
class PaperMetric:
    key: str
    value: int


@dataclass(frozen=True)
class PaperTimingAssumptions:
    """Paper Section 7 / eval-script constants for 64-qubit VQE/SPSA."""

    target_cycle_ns: float = TARGET_CYCLE_NS
    baseline_total_ns: float = 204_300_000.0
    baseline_quantum_host_comm_ns: float = 18_408_655.7
    baseline_host_computation_ns: float = 160_894_870.8
    qtenon_host_target_cycles: int = 1_338_502
    qtenon_schedule_removed_target_cycles: int = 3_356_063
    cycle_tolerance: int = 64
    qtenon_without_software_comm_ns: float = 5_424.0 + 194.0 * 20.0
    qtenon_comm_ns: float = 5_424.0 + 70.0 * 20.0
    qtenon_pulse_generation_ns: float = 665_907.0
    quantum_execution_ns: float = 16_060_020.0

    @property
    def baseline_pulse_generation_ns(self) -> float:
        return (
            self.baseline_total_ns
            - self.quantum_execution_ns
            - self.baseline_quantum_host_comm_ns
            - self.baseline_host_computation_ns
        )


DEFAULT_TIMING_ASSUMPTIONS = PaperTimingAssumptions()


@dataclass(frozen=True)
class PaperBreakdownRow:
    scenario: str
    component: str
    component_ns: float
    total_ns: float
    source: str

    @property
    def total_ms(self) -> float:
        return self.total_ns / 1_000_000.0

    @property
    def component_ms(self) -> float:
        return self.component_ns / 1_000_000.0

    @property
    def component_percent(self) -> float:
        return 100.0 * self.component_ns / self.total_ns


@dataclass(frozen=True)
class PaperExperimentLog:
    source: Literal["live", "capture"]
    metrics: tuple[PaperMetric, ...]
    raw_text: str

    def metric(self, key: str) -> int:
        for metric in self.metrics:
            if metric.key == key:
                return metric.value
        raise KeyError(key)

    def breakdown_for(self, scenario: str) -> list[PaperBreakdownRow]:
        rows = [row for row in derive_vqe_spsa_time_breakdown(self) if row.scenario == scenario]
        return sorted(rows, key=lambda row: COMPONENT_ORDER.index(row.component))


@dataclass(frozen=True)
class PaperExperimentArtifacts:
    """Bundle returned by live or replay execution for the notebook."""

    source: Literal["live", "capture"]
    paths: TutorialPaths
    run_dir: Path
    trace_text: str
    log_text: str
    objdump_text: str
    capture: StaticCapture | None = None
    compile_result: CompileResult | None = None
    run_result: LocalRunResult | None = None
    elf_path: Path | None = None
    simulator_path: Path | None = None
    parsed: PaperExperimentLog | None = None


_METRIC_RE = re.compile(r"^metric,([^,]+),([0-9]+)$")


def load_paper_vqe_capture(paths: TutorialPaths) -> StaticCapture:
    return load_capture_static(paths.captures_dir, PAPER_VQE_CAPTURE)


def parse_paper_vqe_log(text: str, *, source: Literal["live", "capture"] = "capture") -> PaperExperimentLog:
    metrics: list[PaperMetric] = []

    for raw_line in text.splitlines():
        metric_match = _METRIC_RE.match(raw_line.strip())
        if metric_match is not None:
            metrics.append(PaperMetric(metric_match.group(1), int(metric_match.group(2))))

    if not metrics:
        raise PaperExperimentParseError("No metric rows found in paper_vqe_spsa log.")
    log = PaperExperimentLog(source=source, metrics=tuple(metrics), raw_text=text)
    _validate_vqe_spsa_metrics(log)
    return log


def _validate_vqe_spsa_metrics(log: PaperExperimentLog) -> None:
    required = (
        "qubits",
        "shots",
        "iterations",
        "parameters",
        "q_set_calls",
        "q_update_calls",
        "q_gen_calls",
        "q_run_calls",
        "total_cycles",
        "qtenon_host_cycles_rdcycle",
        "qtenon_schedule_removed_cycles_rdcycle",
        "qtenon_without_software_host_cycles_rdcycle",
        "qtenon_host_target_cycles",
        "qtenon_schedule_removed_target_cycles",
    )
    missing = [key for key in required if not any(metric.key == key for metric in log.metrics)]
    if missing:
        joined = ", ".join(missing)
        raise PaperExperimentParseError(f"Missing required paper_vqe_spsa metric rows: {joined}.")


def _metric_close(
    log: PaperExperimentLog,
    measured_key: str,
    target_key: str,
    *,
    tolerance: int,
) -> None:
    measured = log.metric(measured_key)
    target = log.metric(target_key)
    if abs(measured - target) > tolerance:
        raise PaperExperimentParseError(
            f"{measured_key}={measured} does not match {target_key}={target} "
            f"within tolerance {tolerance}."
        )


def _row(scenario: str, component: str, component_ns: float, total_ns: float, source: str) -> PaperBreakdownRow:
    return PaperBreakdownRow(
        scenario=scenario,
        component=component,
        component_ns=component_ns,
        total_ns=total_ns,
        source=source,
    )


def derive_vqe_spsa_time_breakdown(
    log: PaperExperimentLog,
    assumptions: PaperTimingAssumptions = DEFAULT_TIMING_ASSUMPTIONS,
) -> tuple[PaperBreakdownRow, ...]:
    """Rebuild the paper's VQE/SPSA time-breakdown rows.

    ``paper_vqe_spsa.c`` emits raw benchmark metrics from a Verilator run. The
    Qtenon host terms are consumed from those rdcycle metrics at 1 GHz; quantum
    execution, pulse generation, communication, and the decoupled baseline use
    the Section 7 / archived eval-script model.
    """

    if log.metric("qubits") != 64:
        raise PaperExperimentParseError("VQE/SPSA time_breakdown derivation expects 64 qubits.")
    if log.metric("shots") != 500:
        raise PaperExperimentParseError("VQE/SPSA time_breakdown derivation expects 500 shots.")
    if log.metric("iterations") != 10:
        raise PaperExperimentParseError("VQE/SPSA time_breakdown derivation expects 10 iterations.")
    _metric_close(
        log,
        "qtenon_host_cycles_rdcycle",
        "qtenon_host_target_cycles",
        tolerance=assumptions.cycle_tolerance,
    )
    _metric_close(
        log,
        "qtenon_schedule_removed_cycles_rdcycle",
        "qtenon_schedule_removed_target_cycles",
        tolerance=assumptions.cycle_tolerance,
    )

    baseline_total = assumptions.baseline_total_ns
    qtenon_host_ns = log.metric("qtenon_host_cycles_rdcycle") * assumptions.target_cycle_ns
    qtenon_without_software_host_ns = (
        log.metric("qtenon_without_software_host_cycles_rdcycle") * assumptions.target_cycle_ns
    )
    qtenon_without_software_total = (
        assumptions.quantum_execution_ns
        + assumptions.qtenon_without_software_comm_ns
        + assumptions.qtenon_pulse_generation_ns
        + qtenon_without_software_host_ns
    )
    qtenon_total = (
        assumptions.quantum_execution_ns
        + assumptions.qtenon_comm_ns
        + assumptions.qtenon_pulse_generation_ns
        + qtenon_host_ns
    )

    return (
        _row("baseline", "quantum_execution", assumptions.quantum_execution_ns, baseline_total, "paper_quantum_model"),
        _row("baseline", "quantum_host_comm", assumptions.baseline_quantum_host_comm_ns, baseline_total, "baseline_model"),
        _row("baseline", "pulse_generation", assumptions.baseline_pulse_generation_ns, baseline_total, "baseline_model"),
        _row("baseline", "host_computation", assumptions.baseline_host_computation_ns, baseline_total, "baseline_rdcycle_1ghz"),
        _row("qtenon_without_software", "quantum_execution", assumptions.quantum_execution_ns, qtenon_without_software_total, "paper_quantum_model"),
        _row("qtenon_without_software", "quantum_host_comm", assumptions.qtenon_without_software_comm_ns, qtenon_without_software_total, "paper_eval_script"),
        _row("qtenon_without_software", "pulse_generation", assumptions.qtenon_pulse_generation_ns, qtenon_without_software_total, "paper_eval_script"),
        _row("qtenon_without_software", "host_computation", qtenon_without_software_host_ns, qtenon_without_software_total, "verilator_rdcycle"),
        _row("qtenon", "quantum_execution", assumptions.quantum_execution_ns, qtenon_total, "paper_quantum_model"),
        _row("qtenon", "quantum_host_comm", assumptions.qtenon_comm_ns, qtenon_total, "paper_eval_script"),
        _row("qtenon", "pulse_generation", assumptions.qtenon_pulse_generation_ns, qtenon_total, "paper_eval_script"),
        _row("qtenon", "host_computation", qtenon_host_ns, qtenon_total, "verilator_rdcycle"),
    )


def paper_breakdown_plot_rows(log: PaperExperimentLog) -> dict[str, list[PaperBreakdownRow]]:
    return {scenario: log.breakdown_for(scenario) for scenario in SCENARIO_ORDER}


def paper_breakdown_table_rows(log: PaperExperimentLog) -> list[list[object]]:
    rows: list[list[object]] = []
    for scenario in SCENARIO_ORDER:
        for row in log.breakdown_for(scenario):
            rows.append([
                SCENARIO_LABELS[row.scenario],
                COMPONENT_LABELS[row.component],
                row.total_ms,
                row.component_ms,
                row.component_percent,
                row.source,
            ])
    return rows


def run_paper_vqe_spsa(
    paths: TutorialPaths,
    run_dir: Path,
    *,
    live: bool,
) -> PaperExperimentArtifacts:
    """Execute or replay the VQE/SPSA paper figure workload."""

    if not live:
        capture = load_paper_vqe_capture(paths)
        parsed = parse_paper_vqe_log(capture.log_text, source="capture")
        return PaperExperimentArtifacts(
            source="capture",
            paths=paths,
            run_dir=run_dir,
            trace_text=capture.trace_text,
            log_text=capture.log_text,
            objdump_text=capture.objdump_text,
            capture=capture,
            parsed=parsed,
        )

    src = paths.tests_dir / PAPER_VQE_SOURCE
    elf_path = run_dir / "paper_vqe_spsa.elf"
    simulator_path = ensure_simulator(paths.chipyard_root, paths.config_name)
    compile_result = compile_elf(src, elf_path)
    run_result = run_local_sim(
        simulator_path,
        elf_path,
        run_dir,
        chipyard_root=paths.chipyard_root,
        config_name=paths.config_name,
        fast=True,
        sim_flags=[f"+max-cycles={PAPER_VQE_MAX_CYCLES}"],
    )
    objdump_path = elf_path.with_suffix(elf_path.suffix + ".objdump.txt")
    parsed = parse_paper_vqe_log(run_result.log_path.read_text(encoding="utf-8"), source="live")
    return PaperExperimentArtifacts(
        source="live",
        paths=paths,
        run_dir=run_dir,
        trace_text=run_result.trace_path.read_text(encoding="utf-8"),
        log_text=run_result.log_path.read_text(encoding="utf-8"),
        objdump_text=objdump_path.read_text(encoding="utf-8"),
        compile_result=compile_result,
        run_result=run_result,
        elf_path=elf_path,
        simulator_path=simulator_path,
        parsed=parsed,
    )
