"""Parse tutorial trace lines and recover the custom0 command stream."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Literal

from .encode import CUSTOM0_OPCODE, decode_instruction, identify_command

PathLabel = Literal["①", "②", "—"]

_PATH_CLASSIFICATION: dict[str, PathLabel] = {
    "q_update": "①",
    "q_set": "②",
    "q_acquire": "②",
    "q_gen": "—",
    "q_run": "—",
}

INST_PATTERN = re.compile(r"inst=\[([0-9a-fA-F]{8,16})\]")
PC_PATTERN = re.compile(r"pc=\[([0-9a-fA-F]+)\]")
CYCLE_PATTERN = re.compile(r"^C\d+:\s+(\d+)\s+\[\d+\]")


@dataclass(frozen=True)
class TraceInstruction:
    """A decoded instruction recovered from one trace line."""

    line_number: int
    cycle: int | None
    instruction: int
    raw_line: str
    pc: int | None
    decoded: dict[str, int]
    command: str | None


def _candidate_words(line: str) -> list[int]:
    """Return candidate 32-bit words from a trace line.

    Only trusts the explicit ``inst=[...]`` field emitted by chipyard's
    spike-dasm layer. An earlier implementation also scanned any 8-hex
    token on the line as a fallback; that over-matched trailing bytes of
    register-value dumps (e.g. ``W[r 6=000000008000240b]`` whose low
    byte ``0x0b`` equals the RoCC ``custom0`` opcode), so *every* retire
    line got classified as a phantom custom0. The fallback is gone.
    """

    candidates: list[int] = []
    seen: set[int] = set()
    for match in INST_PATTERN.findall(line):
        word = int(match, 16) & 0xFFFFFFFF
        if word not in seen:
            candidates.append(word)
            seen.add(word)
    return candidates


def extract_instruction_word(line: str, *, opcode: int = CUSTOM0_OPCODE) -> int | None:
    """Extract the first 32-bit word on a line that matches the desired opcode."""

    for word in _candidate_words(line):
        if word & 0x7F == opcode:
            return word
    return None


def filter_trace(raw_text: str, *, opcode: int = CUSTOM0_OPCODE) -> str:
    """Keep only lines that carry a recognised instruction word or the simulator $finish marker.

    Mirrors the filter used by ``capture artifact generation flow`` so that
    live simulator runs and the archive capture pipeline share a single
    implementation. The output preserves original line ordering and always
    ends with a trailing newline when any lines are kept.
    """

    kept: list[str] = []
    for line in raw_text.splitlines():
        if extract_instruction_word(line, opcode=opcode) is not None or "Verilog $finish" in line:
            kept.append(line)
    if not kept:
        return ""
    return "\n".join(kept) + "\n"


def classify_path(command_name: str | None) -> PathLabel:
    """Classify a custom0 command name into its demo path symbol.

    ``q_update`` is the generate-then-store path (①). ``q_set`` and
    ``q_acquire`` are the explicit set/read data-motion path (②). The
    pure-compute commands ``q_gen`` and ``q_run`` — plus any unknown name —
    fall outside the ①/② taxonomy and map to the dash glyph (—).
    """

    if command_name is None:
        return "—"
    return _PATH_CLASSIFICATION.get(command_name, "—")


def parse_trace_lines(lines: Iterable[str], *, opcode: int = CUSTOM0_OPCODE) -> list[TraceInstruction]:
    """Parse a trace stream and return every matching custom instruction."""

    parsed: list[TraceInstruction] = []
    for index, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        word = extract_instruction_word(line, opcode=opcode)
        if word is None:
            continue

        pc_match = PC_PATTERN.search(line)
        cycle_match = CYCLE_PATTERN.search(line)
        decoded = decode_instruction(word)
        parsed.append(
            TraceInstruction(
                line_number=index,
                cycle=int(cycle_match.group(1)) if cycle_match else None,
                instruction=word,
                raw_line=line,
                pc=int(pc_match.group(1), 16) if pc_match else None,
                decoded=decoded,
                command=identify_command(decoded),
            )
        )
    return parsed


def parse_trace_text(text: str, *, opcode: int = CUSTOM0_OPCODE) -> list[TraceInstruction]:
    """Parse a full trace blob in one call."""

    return parse_trace_lines(text.splitlines(), opcode=opcode)


def parse_trace_file(path: str | Path, *, opcode: int = CUSTOM0_OPCODE) -> list[TraceInstruction]:
    """Load and parse a trace file from disk."""

    return parse_trace_text(Path(path).read_text(encoding="utf-8"), opcode=opcode)


def filter_instructions(
    instructions: Iterable[TraceInstruction],
    *,
    funct7: int | None = None,
    command: str | None = None,
) -> list[TraceInstruction]:
    """Filter decoded instructions by funct7 or recognized command name."""

    results = list(instructions)
    if funct7 is not None:
        results = [entry for entry in results if entry.decoded["funct7"] == funct7]
    if command is not None:
        results = [entry for entry in results if entry.command == command]
    return results


def split_hybrid_iterations(instructions: Iterable[TraceInstruction]) -> list[list[TraceInstruction]]:
    """Split a custom-instruction stream into `q_set/q_update -> ... -> q_acquire` windows."""

    groups: list[list[TraceInstruction]] = []
    current: list[TraceInstruction] = []

    for entry in instructions:
        if entry.command in {"q_set", "q_update"}:
            if current:
                groups.append(current)
                current = []
        if not current and entry.command not in {"q_set", "q_update"}:
            continue

        current.append(entry)
        if entry.command == "q_acquire":
            groups.append(current)
            current = []

    if current:
        groups.append(current)
    return groups
