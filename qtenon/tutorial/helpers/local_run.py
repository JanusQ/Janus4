"""Local-run helpers: subprocess wrappers around the chipyard RISC-V toolchain and Verilator.

This module owns the "live" side of the tutorial's replay pipeline — it
cross-compiles the hybrid_loop ELF, idempotently builds the chipyard
Verilator simulator, and invokes ``make run-binary`` to produce the
filtered trace + UART log the notebook renders at cell [14].

It is intentionally separate from ``archive.py`` (pure text IO over the
checked-in ``tutorial/captures/`` archive): the two concerns only share
:class:`TutorialPaths`, and ``local_run`` is the one that shells out.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Literal

from .trace import filter_trace, parse_trace_text


class ToolchainMissing(RuntimeError):
    """Raised when ``riscv64-unknown-elf-gcc`` or ``make`` is not on PATH, or the chipyard tree is absent."""


class VerilatorMissing(RuntimeError):
    """Raised when the ``verilator`` binary is unavailable or the simulator build fails."""


@dataclass(frozen=True)
class CompileResult:
    """ELF + objdump produced by a local ``riscv64-unknown-elf-gcc`` invocation."""

    elf_path: Path
    elf_bytes: int
    wall_seconds: float


@dataclass(frozen=True)
class LocalRunResult:
    """Outcome of a local ``simulator +verbose ... <elf>`` run."""

    trace_path: Path
    log_path: Path
    trace_bytes: int
    log_bytes: int
    cycle_count: int
    custom0_count: int
    wall_seconds: float


@dataclass(frozen=True)
class LiveRun:
    """Cell 14 live/fallback packaging of the trace + log + objdump the notebook renders."""

    source: Literal["live", "fallback"]
    trace_text: str
    log_text: str
    objdump_text: str
    run_dir: Path


def _tool_prefix(toolchain: str) -> str:
    """Derive ``riscv64-unknown-elf-`` from ``riscv64-unknown-elf-gcc``."""

    if toolchain.endswith("-gcc"):
        return toolchain[: -len("gcc")]
    return toolchain + "-"


def compile_elf(
    src: Path,
    elf_out: Path,
    *,
    toolchain: str = "riscv64-unknown-elf-gcc",
    extra_args: list[str] | None = None,
) -> "CompileResult":
    """Compile ``src`` into a statically linked RISC-V ELF suitable for the local simulator.

    Assembles the chipyard test flag set used by ``refresh_captures.sh``'s
    remote make (``-std=gnu99 -O2 -fno-common -fno-builtin-printf -Wall
    -march=rv64imafdc -mabi=lp64d -static -specs=htif_nano.specs``) and
    writes a raw objdump next to the ELF as ``<elf_out>.objdump.txt``.
    ``htif_nano.specs`` ships with conda ``riscv-tools`` and supplies the
    crt and linker script, so no hand-written linker input is required.
    The objdump is left un-annotated here; ``refresh_captures.sh`` owns
    the ``annotate_objdump`` step, and cell 14's live path does not
    depend on the `# q_*` comment decoration.

    ``extra_args`` is appended verbatim to the gcc invocation so callers
    can inject defines (e.g. ``["-DFOO=1"]``) without subclassing.

    Raises :class:`ToolchainMissing` when either the C compiler or
    ``objdump`` is absent from ``PATH``.
    """

    elf_out.parent.mkdir(parents=True, exist_ok=True)
    objdump_path = elf_out.with_suffix(elf_out.suffix + ".objdump.txt")

    compile_argv: list[str] = [
        toolchain,
        "-std=gnu99",
        "-O2",
        "-fno-common",
        "-fno-builtin-printf",
        "-Wall",
        "-march=rv64imafdc",
        "-mabi=lp64d",
        "-static",
        "-specs=htif_nano.specs",
        str(src),
        "-o",
        str(elf_out),
    ]
    if extra_args:
        compile_argv.extend(extra_args)
    objdump_cmd = _tool_prefix(toolchain) + "objdump"
    objdump_argv: list[str] = [objdump_cmd, "-d", str(elf_out)]

    start = time.monotonic()
    try:
        subprocess.run(compile_argv, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ToolchainMissing(f"{toolchain} not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise ToolchainMissing(
            f"{toolchain} exited with status {exc.returncode}: {exc.stderr}"
        ) from exc

    try:
        objdump_result = subprocess.run(
            objdump_argv, check=True, capture_output=True, text=True
        )
    except FileNotFoundError as exc:
        raise ToolchainMissing(f"{objdump_cmd} not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise ToolchainMissing(
            f"{objdump_cmd} exited with status {exc.returncode}: {exc.stderr}"
        ) from exc
    wall = time.monotonic() - start

    objdump_path.write_text(objdump_result.stdout, encoding="utf-8")

    return CompileResult(
        elf_path=elf_out,
        elf_bytes=elf_out.stat().st_size,
        wall_seconds=wall,
    )


def ensure_simulator(chipyard_root: Path, config_name: str) -> Path:
    """Idempotently build the chipyard verilator simulator binary and return its path.

    Mirrors the ``make -C ${REMOTE_SIM_DIR} CONFIG=${CONFIG_NAME}`` shape
    from ``refresh_captures.sh``. The caller is expected to have already
    sourced ``tutorial_env.sh`` (or equivalent) so that ``verilator`` and
    the RISC-V toolchain are discoverable from ``PATH``.

    Failure taxonomy:
    - chipyard tree missing, or ``make`` / ``riscv64-unknown-elf-gcc`` off
      ``PATH`` → :class:`ToolchainMissing`.
    - ``verilator`` missing, or the C++ build step exits non-zero →
      :class:`VerilatorMissing`.
    """

    sim_dir = chipyard_root / "sims" / "verilator"
    if not sim_dir.is_dir():
        raise ToolchainMissing(f"chipyard verilator sim dir not found: {sim_dir}")
    if shutil.which("make") is None:
        raise ToolchainMissing("make not found on PATH")
    if shutil.which("riscv64-unknown-elf-gcc") is None:
        raise ToolchainMissing("riscv64-unknown-elf-gcc not found on PATH")
    if shutil.which("verilator") is None:
        raise VerilatorMissing("verilator not found on PATH")

    make_argv: list[str] = [
        "make",
        "-C",
        str(sim_dir),
        f"CONFIG={config_name}",
    ]
    try:
        subprocess.run(make_argv, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ToolchainMissing("make not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise VerilatorMissing(
            f"verilator simulator build failed (exit {exc.returncode}): {exc.stderr}"
        ) from exc

    # Prefer the canonical chipyard 1.12+ name, but fall back to any
    # simulator-*-{config_name} executable the build dropped in sim_dir.
    # Motivation:
    # - some chipyard forks drop the ".harness" infix
    #   ("simulator-chipyard-{config}")
    # - the debug / verbose variants append a suffix
    #   ("simulator-chipyard.harness-{config}-debug")
    # - none of the five ISA bits this tutorial exercises depend on that
    #   naming, so any executable simulator for the right CONFIG is fine.
    exact = sim_dir / f"simulator-chipyard.harness-{config_name}"
    if exact.is_file():
        return exact
    candidates = sorted(sim_dir.glob(f"simulator-*-{config_name}"))
    candidates = [c for c in candidates if c.is_file() and os.access(c, os.X_OK)]
    if candidates:
        return candidates[0]
    raise VerilatorMissing(
        f"no simulator binary for CONFIG={config_name} under {sim_dir}"
    )


def run_local_sim(
    simulator: Path,
    elf: Path,
    out_dir: Path,
    *,
    chipyard_root: Path,
    config_name: str,
) -> "LocalRunResult":
    """Run the chipyard verilator simulator on ``elf`` via ``make run-binary``.

    Delegates to chipyard's ``sims/verilator/Makefile`` (target
    ``run-binary``) so the invocation matches what ``refresh_captures.sh``
    does remotely: correct ``+permissive / +dramsim / +max-cycles /
    +verbose`` flags, stderr piped through ``spike-dasm`` into
    ``{elf.stem}.out``, stdout ``tee``'d into ``{elf.stem}.log``. Those
    two chipyard-produced files are then copied back into ``out_dir`` as
    ``{elf.stem}.trace.txt`` (filtered via
    :func:`tutorial.helpers.trace.filter_trace`, same filter as the
    archive pipeline) and ``{elf.stem}.log`` respectively.

    ``chipyard_root`` and ``config_name`` are passed in explicitly by the
    caller (notebook cell [14] reads them from ``PreparedRun`` so they
    stay synchronised with :func:`ensure_simulator`). Deriving them from
    ``simulator.parent.parent`` / ``simulator.name.rsplit("-", 1)`` was
    brittle: symlinked simulators broke the parent lookup, CONFIG names
    containing hyphens broke the rsplit, and non-standard chipyard forks
    emit different simulator-binary names entirely.

    ``cycle_count`` is the last parseable ``C<core>: <cycle>`` column of
    the filtered trace; ``custom0_count`` is
    ``len(parse_trace_text(trace_text))``.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{elf.stem}.log"
    trace_path = out_dir / f"{elf.stem}.trace.txt"

    if not simulator.is_file():
        raise VerilatorMissing(f"simulator binary not found: {simulator}")

    sim_dir = chipyard_root / "sims" / "verilator"
    chipyard_output = (
        sim_dir / "output" / f"chipyard.harness.TestHarness.{config_name}"
    )

    make_argv: list[str] = [
        "make",
        "-C",
        str(sim_dir),
        "run-binary",
        f"CONFIG={config_name}",
        f"BINARY={elf.resolve()}",
    ]

    start = time.monotonic()
    try:
        completed = subprocess.run(
            make_argv,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise VerilatorMissing(f"make not available for run-binary: {exc}") from exc
    wall = time.monotonic() - start

    if completed.returncode != 0:
        raise VerilatorMissing(
            f"make run-binary exited with status {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )

    chipyard_log = chipyard_output / f"{elf.stem}.log"
    chipyard_trace = chipyard_output / f"{elf.stem}.out"
    if not chipyard_log.is_file() or not chipyard_trace.is_file():
        raise VerilatorMissing(
            f"expected run-binary products missing under {chipyard_output}: "
            f"{chipyard_log.name}, {chipyard_trace.name}"
        )

    log_text = chipyard_log.read_text(encoding="utf-8")
    log_path.write_text(log_text, encoding="utf-8")

    trace_raw = chipyard_trace.read_text(encoding="utf-8")
    trace_text = filter_trace(trace_raw)
    trace_path.write_text(trace_text, encoding="utf-8")

    parsed = parse_trace_text(trace_text)
    cycle_count = 0
    for entry in reversed(parsed):
        if entry.cycle is not None:
            cycle_count = entry.cycle
            break
    custom0_count = len(parsed)

    return LocalRunResult(
        trace_path=trace_path,
        log_path=log_path,
        trace_bytes=trace_path.stat().st_size,
        log_bytes=log_path.stat().st_size,
        cycle_count=cycle_count,
        custom0_count=custom0_count,
        wall_seconds=wall,
    )
