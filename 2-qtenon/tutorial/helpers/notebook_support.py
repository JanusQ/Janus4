"""Notebook-facing presentation helpers for the local replay tutorial.

After the Scope 3 split, subprocess wrappers live in
:mod:`tutorial.helpers.local_run` and checked-in archive readers live in
:mod:`tutorial.helpers.archive`. This module keeps plain-text formatting
(``format_table``), log-shape parsers (``parse_hybrid_output`` /
``parse_objdump_custom_commands``), the presentation dataclasses
(``HybridIteration``, ``ObjdumpCommand``, ``ScaleBar``,
``IterationTransfer``, ``SwimlaneSegment``), the three inline-SVG chart
helpers, and ``assert_clean_finish``. It also re-exports every symbol
from ``local_run`` / ``archive`` that the notebook template references so
cells keep a single ``from tutorial.helpers.notebook_support import ...``
import line.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .archive import (
    CaptureMissing,
    ObjdumpLine,
    StaticCapture,
    find_objdump_line,
    load_capture_static,
    source_block,
)
from .local_run import (
    CompileResult,
    LiveRun,
    LocalRunResult,
    ToolchainMissing,
    VerilatorMissing,
    compile_elf,
    ensure_simulator,
    run_local_sim,
)
from .paper_experiment import (
    COMPONENT_LABELS,
    COMPONENT_ORDER,
    DEFAULT_TIMING_ASSUMPTIONS,
    PAPER_VQE_BENCHMARK,
    PAPER_VQE_CAPTURE,
    PAPER_VQE_SOURCE,
    PaperBreakdownRow,
    PaperExperimentArtifacts,
    PaperExperimentLog,
    PaperExperimentParseError,
    PaperMetric,
    PaperTimingAssumptions,
    SCENARIO_LABELS,
    SCENARIO_ORDER,
    derive_vqe_spsa_time_breakdown,
    load_paper_vqe_capture,
    paper_breakdown_plot_rows,
    paper_breakdown_table_rows,
    parse_paper_vqe_log,
    run_paper_vqe_spsa,
)

__all__ = [
    # archive re-exports
    "CaptureMissing",
    "ObjdumpLine",
    "StaticCapture",
    "find_objdump_line",
    "load_capture_static",
    "source_block",
    # local_run re-exports
    "CompileResult",
    "LiveRun",
    "LocalRunResult",
    "ToolchainMissing",
    "VerilatorMissing",
    "compile_elf",
    "ensure_simulator",
    "run_local_sim",
    # paper experiment helpers
    "COMPONENT_LABELS",
    "COMPONENT_ORDER",
    "DEFAULT_TIMING_ASSUMPTIONS",
    "PAPER_VQE_BENCHMARK",
    "PAPER_VQE_CAPTURE",
    "PAPER_VQE_SOURCE",
    "PaperBreakdownRow",
    "PaperExperimentArtifacts",
    "PaperExperimentLog",
    "PaperExperimentParseError",
    "PaperMetric",
    "PaperTimingAssumptions",
    "SCENARIO_LABELS",
    "SCENARIO_ORDER",
    "derive_vqe_spsa_time_breakdown",
    "load_paper_vqe_capture",
    "paper_breakdown_plot_rows",
    "paper_breakdown_table_rows",
    "parse_paper_vqe_log",
    "run_paper_vqe_spsa",
    # local dataclasses
    "HybridIteration",
    "IterationTransfer",
    "ObjdumpCommand",
    "ScaleBar",
    "SwimlaneSegment",
    # local helpers
    "assert_clean_finish",
    "format_table",
    "parse_hybrid_output",
    "parse_objdump_custom_commands",
    # svg helpers
    "bytes_per_iter_bar",
    "path_latency_bar",
    "swimlane_plot",
]

HYBRID_ROW_PATTERN = re.compile(
    r"^(?P<iteration>\d+),"
    r"(?P<theta0_idx>\d+),"
    r"(?P<theta1_idx>\d+),"
    r"(?P<sample_bits>[01]{2}),"
    r"(?P<objective_ppm>\d+),"
    r"(?P<acquire_word>\d+)$"
)
OBJDUMP_CUSTOM_PATTERN = re.compile(
    r"^\s*(?P<address>[0-9a-fA-F]+):\s+"
    r"(?P<word>[0-9a-fA-F]+)\s+"
    r"\.(?:4byte|word)\s+0x[0-9a-fA-F]+\s+#\s+"
    r"(?P<command>q_[a-z]+)\s*$"
)


@dataclass(frozen=True)
class HybridIteration:
    """One tutorial-visible iteration emitted by `hybrid_loop_demo.c`."""

    iteration: int
    theta0_idx: int
    theta1_idx: int
    sample_bits: str
    objective_ppm: int
    acquire_word: int

    @property
    def objective(self) -> float:
        return self.objective_ppm / 1_000_000.0

    @property
    def acquire_word_hex(self) -> str:
        return f"0x{self.acquire_word:016x}"


@dataclass(frozen=True)
class ObjdumpCommand:
    """One custom instruction recovered from an objdump listing."""

    address: int
    word: int
    command: str


@dataclass(frozen=True)
class ScaleBar:
    """One value rendered by the order-of-magnitude latency chart."""

    label: str
    value: float
    note: str
    color: str


@dataclass(frozen=True)
class IterationTransfer:
    """One row for the per-iteration path-usage chart."""

    label: str
    path_i_bytes: float
    path_ii_bytes: float


@dataclass(frozen=True)
class SwimlaneSegment:
    """One labeled interval in the schematic host/controller swimlane."""

    lane: str
    start: float
    end: float
    label: str
    color: str


def assert_clean_finish(text: str) -> None:
    """Raise if a captured log does not terminate with the simulator finish marker."""

    if "Verilog $finish" not in text:
        raise AssertionError("Expected a clean simulator finish marker in the captured output.")


def format_table(headers: list[str], rows: list[list[object]]) -> str:
    """Return a compact monospace table for notebook printing."""

    string_rows = [[str(cell) for cell in headers], *[[str(cell) for cell in row] for row in rows]]
    widths = [max(len(row[index]) for row in string_rows) for index in range(len(headers))]

    def render(row: list[str]) -> str:
        return " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

    divider = "-+-".join("-" * width for width in widths)
    body = [render(string_rows[0]), divider]
    body.extend(render(row) for row in string_rows[1:])
    return "\n".join(body)


def parse_hybrid_output(text: str) -> list[HybridIteration]:
    """Parse CSV-style `hybrid_loop_demo` rows out of mixed simulator stdout."""

    iterations: list[HybridIteration] = []
    for raw_line in text.splitlines():
        match = HYBRID_ROW_PATTERN.match(raw_line.strip())
        if not match:
            continue
        iterations.append(
            HybridIteration(
                iteration=int(match.group("iteration")),
                theta0_idx=int(match.group("theta0_idx")),
                theta1_idx=int(match.group("theta1_idx")),
                sample_bits=match.group("sample_bits"),
                objective_ppm=int(match.group("objective_ppm")),
                acquire_word=int(match.group("acquire_word")),
            )
        )
    return iterations


def parse_objdump_custom_commands(text: str) -> list[ObjdumpCommand]:
    """Recover tutorial-visible custom instructions from an objdump listing."""

    commands: list[ObjdumpCommand] = []
    for raw_line in text.splitlines():
        match = OBJDUMP_CUSTOM_PATTERN.match(raw_line)
        if match is None:
            continue
        commands.append(
            ObjdumpCommand(
                address=int(match.group("address"), 16),
                word=int(match.group("word"), 16),
                command=match.group("command"),
            )
        )
    return commands


def _svg_header(width: int, height: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'


def path_latency_bar(
    bars: list[ScaleBar],
    *,
    title: str = "Latency scale used in the tutorial narrative",
) -> str:
    """Render a log-scale order-of-magnitude bar chart as inline SVG."""

    if not bars:
        raise ValueError("Expected at least one latency bar.")
    if any(bar.value <= 0 for bar in bars):
        raise ValueError("Latency bars must be strictly positive.")

    width = 920
    height = 360
    left = 120
    right = 36
    top = 72
    bottom = 64
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_log = max(math.log10(bar.value) for bar in bars)

    def bar_width(value: float) -> float:
        return plot_width * math.log10(value) / max_log if value > 1 else plot_width * 0.02

    row_height = plot_height / len(bars)
    tick_values = [1.0, 10.0, 1_000.0, 1_000_000.0]
    ticks = []
    for tick in tick_values:
        if tick > max(bar.value for bar in bars):
            continue
        x = left + bar_width(tick)
        ticks.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#d1d5db" stroke-width="1"/>'
            f'<text x="{x:.1f}" y="{height - 22}" text-anchor="middle" '
            f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#6b7280">{int(tick):,} ns</text>'
        )

    bars_svg = []
    for index, bar in enumerate(bars):
        y = top + index * row_height + 14
        h = row_height - 28
        w = bar_width(bar.value)
        bars_svg.append(
            f'<text x="{left - 16}" y="{y + h / 2 + 4:.1f}" text-anchor="end" '
            f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="13" fill="#111827">{bar.label}</text>'
            f'<rect x="{left}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" fill="{bar.color}" opacity="0.90"/>'
            f'<text x="{left + w + 12:.1f}" y="{y + h / 2 + 4:.1f}" '
            f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="12" fill="#111827">{bar.note}</text>'
        )

    return (
        _svg_header(width, height)
        + """
  <rect x="0" y="0" width="920" height="360" rx="18" fill="#f8fafc" stroke="#cbd5e1"/>
"""
        + f'  <text x="{width / 2:.1f}" y="32" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">{title}</text>\n'
        + f'  <text x="{width / 2:.1f}" y="54" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="12" fill="#475569">The red bar is a paper-scale reference; the on-chip bars are the tutorial&apos;s order-of-magnitude guide.</text>\n'
        + "".join(ticks)
        + "".join(bars_svg)
        + "</svg>"
    )


def bytes_per_iter_bar(
    rows: list[IterationTransfer],
    *,
    title: str = "Bytes moved per iteration",
) -> str:
    """Render a stacked per-iteration byte chart as inline SVG."""

    if not rows:
        raise ValueError("Expected at least one iteration row.")

    width = 860
    height = 360
    left = 88
    right = 32
    top = 70
    bottom = 62
    plot_width = width - left - right
    plot_height = height - top - bottom
    gap = 24
    bar_width = (plot_width - gap * (len(rows) - 1)) / len(rows)
    max_total = max(row.path_i_bytes + row.path_ii_bytes for row in rows) or 1.0

    def scaled_height(value: float) -> float:
        return plot_height * value / max_total

    bars = []
    for index, row in enumerate(rows):
        x = left + index * (bar_width + gap)
        path_ii_h = scaled_height(row.path_ii_bytes)
        path_i_h = scaled_height(row.path_i_bytes)
        bars.append(
            f'<rect x="{x:.1f}" y="{top + plot_height - path_ii_h:.1f}" width="{bar_width:.1f}" height="{path_ii_h:.1f}" rx="10" fill="#f59e0b" opacity="0.92"/>'
            f'<rect x="{x:.1f}" y="{top + plot_height - path_ii_h - path_i_h:.1f}" width="{bar_width:.1f}" height="{path_i_h:.1f}" rx="10" fill="#0f766e" opacity="0.96"/>'
            f'<text x="{x + bar_width / 2:.1f}" y="{height - 24}" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="12" fill="#334155">{row.label}</text>'
            f'<text x="{x + bar_width / 2:.1f}" y="{top + plot_height - path_ii_h - path_i_h - 8:.1f}" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#111827">{row.path_i_bytes + row.path_ii_bytes:.0f} B</text>'
        )

    return (
        _svg_header(width, height)
        + f"""
  <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#f8fafc" stroke="#cbd5e1"/>
  <text x="{width / 2:.1f}" y="32" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">{title}</text>
  <text x="{width / 2:.1f}" y="54" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="12" fill="#475569">Green = Path ① register update, Amber = Path ② bulk or measurement traffic</text>
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#94a3b8" stroke-width="2"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#94a3b8" stroke-width="2"/>
  <text x="{left - 12}" y="{top + 4}" text-anchor="end" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#6b7280">{max_total:.0f} B</text>
  <text x="{left - 12}" y="{top + plot_height + 4}" text-anchor="end" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#6b7280">0 B</text>
  <rect x="{width - 210}" y="76" width="12" height="12" rx="3" fill="#0f766e"/>
  <text x="{width - 192}" y="86" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#111827">Path ①</text>
  <rect x="{width - 136}" y="76" width="12" height="12" rx="3" fill="#f59e0b"/>
  <text x="{width - 118}" y="86" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#111827">Path ②</text>
"""
        + "".join(bars)
        + "</svg>"
    )


def swimlane_plot(
    segments: list[SwimlaneSegment],
    *,
    title: str = "Schematic host/controller swimlane",
) -> str:
    """Render a two-lane timeline as inline SVG."""

    if not segments:
        raise ValueError("Expected at least one swimlane segment.")

    width = 980
    height = 320
    left = 96
    right = 32
    top = 76
    plot_width = width - left - right
    lane_height = 72
    lane_gap = 44
    max_end = max(segment.end for segment in segments)
    if max_end <= 0:
        raise ValueError("Swimlane segments must end after time zero.")

    def scaled_x(value: float) -> float:
        return left + plot_width * value / max_end

    lane_y = {
        "Host": top,
        "Controller": top + lane_height + lane_gap,
    }
    bars = []
    for segment in segments:
        if segment.lane not in lane_y:
            raise ValueError(f"Unknown swimlane: {segment.lane}")
        x = scaled_x(segment.start)
        w = max(scaled_x(segment.end) - x, 10.0)
        y = lane_y[segment.lane]
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{lane_height:.1f}" rx="14" fill="{segment.color}" opacity="0.92"/>'
            f'<text x="{x + w / 2:.1f}" y="{y + lane_height / 2 + 4:.1f}" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#111827">{segment.label}</text>'
        )

    return (
        _svg_header(width, height)
        + f"""
  <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#f8fafc" stroke="#cbd5e1"/>
  <text x="{width / 2:.1f}" y="32" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">{title}</text>
  <text x="{width / 2:.1f}" y="54" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="12" fill="#475569">The replay trace gives instruction timing, so this diagram is intentionally schematic rather than a full waveform.</text>
  <text x="{left - 18}" y="{top + lane_height / 2 + 4:.1f}" text-anchor="end" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="14" font-weight="700" fill="#111827">Host</text>
  <text x="{left - 18}" y="{top + lane_height + lane_gap + lane_height / 2 + 4:.1f}" text-anchor="end" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="14" font-weight="700" fill="#111827">Controller</text>
  <line x1="{left}" y1="{top + lane_height}" x2="{left + plot_width}" y2="{top + lane_height}" stroke="#cbd5e1" stroke-width="1"/>
  <line x1="{left}" y1="{top + lane_height + lane_gap + lane_height}" x2="{left + plot_width}" y2="{top + lane_height + lane_gap + lane_height}" stroke="#cbd5e1" stroke-width="1"/>
  <line x1="{left}" y1="{top - 18}" x2="{left + plot_width}" y2="{top - 18}" stroke="#94a3b8" stroke-width="2"/>
  <text x="{left}" y="{top - 24}" text-anchor="start" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#6b7280">cycle 0</text>
  <text x="{left + plot_width}" y="{top - 24}" text-anchor="end" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="11" fill="#6b7280">cycle {max_end:.0f}</text>
"""
        + "".join(bars)
        + "</svg>"
    )
