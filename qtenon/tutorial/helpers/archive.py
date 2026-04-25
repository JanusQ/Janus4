"""Archive helpers: pure file IO over the checked-in ``captures/hybrid_loop`` archive.

Split off from ``notebook_support.py`` so the live-run code path
(``local_run.py``: subprocess wrappers) stays separate from the static
replay reader used by cells [3] / [8] / [10]. Everything in this module
is side-effect free text IO — no subprocess, no simulator, no toolchain
PATH lookup. The archive is treated as an immutable data file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class StaticCapture:
    """Plain text + path bundle for a checked-in capture archive.

    The archive reader path intentionally avoids the elf binary and the
    `assert_clean_finish` side effect so archive loads stay pure text IO.
    """

    trace_text: str
    objdump_text: str
    log_text: str
    trace_path: Path
    objdump_path: Path
    log_path: Path


@dataclass(frozen=True)
class ObjdumpLine:
    """One custom0-instruction line recovered from an objdump listing."""

    pc_hex: str       # zero-padded 16 hex chars, lowercase
    hex_word: str     # zero-padded 8 hex chars, lowercase
    raw_line: str


class CaptureMissing(FileNotFoundError):
    """Raised when ``captures/<name>/`` archive is not present or incomplete."""


def load_capture_static(captures_dir: Path, name: str = "hybrid_loop") -> StaticCapture:
    """Load the three text files of a checked-in capture archive by name.

    Reads ``captures_dir/<name>/<name>.trace.txt``,
    ``captures_dir/<name>/<name>.objdump.txt``, and
    ``captures_dir/<name>/<name>.log``. Any missing file (or missing
    directory) raises :class:`CaptureMissing` with a path-bearing message.
    """

    capture_dir = captures_dir / name
    if not capture_dir.is_dir():
        raise CaptureMissing(f"Missing capture directory: {capture_dir}")

    trace_path = capture_dir / f"{name}.trace.txt"
    objdump_path = capture_dir / f"{name}.objdump.txt"
    log_path = capture_dir / f"{name}.log"
    for required in (trace_path, objdump_path, log_path):
        if not required.is_file():
            raise CaptureMissing(f"Missing capture archive file: {required}")

    return StaticCapture(
        trace_text=trace_path.read_text(encoding="utf-8"),
        objdump_text=objdump_path.read_text(encoding="utf-8"),
        log_text=log_path.read_text(encoding="utf-8"),
        trace_path=trace_path,
        objdump_path=objdump_path,
        log_path=log_path,
    )


def source_block(path: Path, start_marker: str, end_marker: str) -> str:
    """Extract an inclusive text block bounded by two marker substrings.

    Returns the text from the first line containing ``start_marker`` through
    the next line containing ``end_marker`` (both inclusive). Used by the
    notebook to lift ``q_*`` macro bodies out of ``rocc.h``.

    Raises :class:`ValueError` if ``start_marker`` is not found, or if
    ``start_marker`` is found but no subsequent line contains ``end_marker``.
    """

    lines = path.read_text(encoding="utf-8").splitlines()
    start_idx: int | None = None
    for index, line in enumerate(lines):
        if start_marker in line:
            start_idx = index
            break
    if start_idx is None:
        raise ValueError(f"Start marker {start_marker!r} not found in {path}")

    for end_idx in range(start_idx, len(lines)):
        if end_marker in lines[end_idx]:
            return "\n".join(lines[start_idx : end_idx + 1])
    raise ValueError(
        f"End marker {end_marker!r} not found after start marker "
        f"{start_marker!r} in {path}"
    )


def find_objdump_line(objdump_text: str, pc: int, word: int) -> ObjdumpLine:
    """Find the objdump listing line that prints a custom0 instruction at ``pc``.

    objdump renders these lines as e.g.
    ``    80000378:\\t00f6300b          \\t.4byte\\t0xf6300b    # q_set`` —
    the leading pc column drops leading zeros and the ``.4byte`` argument is
    the ``word`` value without leading zeros. The match is case-insensitive
    and tolerant of trailing ``# <command>`` comments and surrounding
    whitespace.

    Raises :class:`ValueError` if no matching line is found.
    """

    pattern = re.compile(
        rf"(?:^|\s)0*{pc:x}:\s+[0-9a-fA-F]+\s+\.4byte\s+0x{word:x}\b",
        re.IGNORECASE,
    )
    for raw_line in objdump_text.splitlines():
        if pattern.search(raw_line):
            return ObjdumpLine(
                pc_hex=f"{pc:016x}",
                hex_word=f"{word:08x}",
                raw_line=raw_line.rstrip(),
            )
    raise ValueError(
        f"No objdump line matched pc=0x{pc:016x} word=0x{word:08x}"
    )
