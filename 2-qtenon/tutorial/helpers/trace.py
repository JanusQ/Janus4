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


@dataclass(frozen=True)
class AcquireCompletionWait:
    """The first host retire visible after a q_acquire command issues."""

    iteration: int
    acquire_line_number: int
    resume_line_number: int
    q_gen_cycle: int | None
    q_run_cycle: int | None
    acquire_cycle: int
    resume_cycle: int

    @property
    def acquire_to_resume_cycles(self) -> int:
        return self.resume_cycle - self.acquire_cycle

    @property
    def gen_to_resume_cycles(self) -> int | None:
        if self.q_gen_cycle is None:
            return None
        return self.resume_cycle - self.q_gen_cycle

    @property
    def run_to_resume_cycles(self) -> int | None:
        if self.q_run_cycle is None:
            return None
        return self.resume_cycle - self.q_run_cycle


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


def extract_trace_cycle(line: str) -> int | None:
    """Extract the Rocket trace cycle column from one retire line."""

    cycle_match = CYCLE_PATTERN.search(line)
    if cycle_match is None:
        return None
    return int(cycle_match.group(1))


def _is_retire_line(line: str) -> bool:
    """Return true for parseable Rocket retire lines, custom or ordinary."""

    return extract_trace_cycle(line) is not None and INST_PATTERN.search(line) is not None


def extract_instruction_word(line: str, *, opcode: int = CUSTOM0_OPCODE) -> int | None:
    """Extract the first 32-bit word on a line that matches the desired opcode."""

    for word in _candidate_words(line):
        if word & 0x7F == opcode:
            return word
    return None


def filter_trace(raw_text: str, *, opcode: int = CUSTOM0_OPCODE) -> str:
    """Keep custom0 lines, q_acquire resume markers, and the simulator $finish marker.

    Mirrors the filter used by ``capture artifact generation flow`` so that
    live simulator runs and the archive capture pipeline share a single
    implementation. The output preserves original line ordering and always
    ends with a trailing newline when any lines are kept.

    A RoCC ``q_acquire`` trace row is the command issue point. If the
    controller is still waiting for a queued ``q_gen``/``q_run`` to complete,
    the completion becomes visible when the host retires its next ordinary
    instruction. The filtered trace therefore keeps the first parseable retire
    line after every ``q_acquire`` in addition to the custom0 rows.
    """

    kept: list[str] = []
    keep_next_retire_after_acquire = False
    for line in raw_text.splitlines():
        word = extract_instruction_word(line, opcode=opcode)
        if word is not None:
            kept.append(line)
            if keep_next_retire_after_acquire and _is_retire_line(line):
                keep_next_retire_after_acquire = False
            command = identify_command(decode_instruction(word))
            if command == "q_acquire":
                keep_next_retire_after_acquire = True
            continue

        if keep_next_retire_after_acquire and _is_retire_line(line):
            kept.append(line)
            keep_next_retire_after_acquire = False
            continue

        if "Verilog $finish" in line:
            kept.append(line)
    if not kept:
        return ""
    return "\n".join(kept) + "\n"


def last_trace_cycle(text: str) -> int | None:
    """Return the last parseable Rocket retire cycle in a trace blob."""

    for line in reversed(text.splitlines()):
        cycle = extract_trace_cycle(line)
        if cycle is not None:
            return cycle
    return None


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
        decoded = decode_instruction(word)
        parsed.append(
            TraceInstruction(
                line_number=index,
                cycle=extract_trace_cycle(line),
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


def parse_acquire_completion_waits(text: str) -> list[AcquireCompletionWait]:
    """Pair each q_acquire issue row with the first following host retire row."""

    lines = text.splitlines()
    instructions = parse_trace_lines(lines)
    waits: list[AcquireCompletionWait] = []

    for iteration_index, group in enumerate(split_hybrid_iterations(instructions)):
        acquire = next((entry for entry in reversed(group) if entry.command == "q_acquire"), None)
        if acquire is None or acquire.cycle is None:
            continue

        resume_line_number: int | None = None
        resume_cycle: int | None = None
        for line_number in range(acquire.line_number + 1, len(lines) + 1):
            line = lines[line_number - 1]
            if extract_instruction_word(line) is not None:
                continue
            cycle = extract_trace_cycle(line)
            if cycle is None:
                continue
            resume_line_number = line_number
            resume_cycle = cycle
            break

        if resume_line_number is None or resume_cycle is None:
            continue

        q_gen = next((entry for entry in group if entry.command == "q_gen"), None)
        q_run = next((entry for entry in group if entry.command == "q_run"), None)
        waits.append(
            AcquireCompletionWait(
                iteration=iteration_index,
                acquire_line_number=acquire.line_number,
                resume_line_number=resume_line_number,
                q_gen_cycle=q_gen.cycle if q_gen else None,
                q_run_cycle=q_run.cycle if q_run else None,
                acquire_cycle=acquire.cycle,
                resume_cycle=resume_cycle,
            )
        )

    return waits
