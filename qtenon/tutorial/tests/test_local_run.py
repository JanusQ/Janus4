"""Unit tests for :mod:`tutorial.helpers.local_run` subprocess wrappers."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tutorial.helpers.encode import pack_q_acquire, pack_q_set
from tutorial.helpers.local_run import (
    CompileResult,
    LocalRunResult,
    ToolchainMissing,
    VerilatorMissing,
    compile_elf,
    ensure_simulator,
    run_local_sim,
)
from tutorial.helpers.trace import parse_trace_text


class CompileElfTest(unittest.TestCase):
    """Fake-subprocess coverage for :func:`compile_elf`.

    None of these tests invoke a real RISC-V toolchain — every
    ``subprocess.run`` call is intercepted by ``mock.patch`` so the suite
    stays green on CI and laptops without ``riscv64-unknown-elf-gcc``.
    """

    def _fake_compile(self, tmp: Path) -> Path:
        """Build a stub ELF file so ``elf_out.stat().st_size`` works."""

        src = tmp / "demo.c"
        src.write_text("int main() { return 0; }\n", encoding="utf-8")
        return src

    def test_compile_elf_builds_chipyard_argv_and_writes_raw_objdump(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._fake_compile(tmp)
            elf_out = tmp / "build" / "demo.elf"

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                if argv[0].endswith("-gcc"):
                    elf_out.parent.mkdir(parents=True, exist_ok=True)
                    elf_out.write_bytes(b"\x7fELFstub-bytes")
                    return SimpleNamespace(stdout="", stderr="", returncode=0)
                if argv[0].endswith("-objdump"):
                    return SimpleNamespace(
                        stdout="demo.elf:     file format elf64-littleriscv\n",
                        stderr="",
                        returncode=0,
                    )
                raise AssertionError(f"Unexpected argv: {argv!r}")

            with mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ) as patched:
                result = compile_elf(src, elf_out)

            self.assertIsInstance(result, CompileResult)
            self.assertEqual(result.elf_path, elf_out)
            self.assertEqual(result.elf_bytes, len(b"\x7fELFstub-bytes"))
            self.assertGreaterEqual(result.wall_seconds, 0.0)

            objdump_path = elf_out.with_suffix(elf_out.suffix + ".objdump.txt")
            self.assertTrue(objdump_path.is_file())
            self.assertIn("elf64-littleriscv", objdump_path.read_text(encoding="utf-8"))

            compile_argv = patched.call_args_list[0].args[0]
            self.assertEqual(compile_argv[0], "riscv64-unknown-elf-gcc")
            for flag in (
                "-std=gnu99",
                "-O2",
                "-fno-common",
                "-fno-builtin-printf",
                "-Wall",
                "-march=rv64imafdc",
                "-mabi=lp64d",
                "-static",
                "-specs=htif_nano.specs",
            ):
                self.assertIn(flag, compile_argv)
            self.assertNotIn("-T", compile_argv)
            self.assertNotIn("link.ld", " ".join(compile_argv))
            self.assertIn(str(src), compile_argv)
            self.assertIn(str(elf_out), compile_argv)

            objdump_argv = patched.call_args_list[1].args[0]
            self.assertEqual(objdump_argv[0], "riscv64-unknown-elf-objdump")
            self.assertEqual(objdump_argv[1], "-d")
            self.assertEqual(objdump_argv[2], str(elf_out))

    def test_compile_elf_appends_extra_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._fake_compile(tmp)
            elf_out = tmp / "demo.elf"

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                if argv[0].endswith("-gcc"):
                    elf_out.write_bytes(b"stub")
                    return SimpleNamespace(stdout="", stderr="", returncode=0)
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ) as patched:
                compile_elf(src, elf_out, extra_args=["-DFOO=1", "-DBAR=2"])

            compile_argv = patched.call_args_list[0].args[0]
            self.assertIn("-DFOO=1", compile_argv)
            self.assertIn("-DBAR=2", compile_argv)
            # extras appear after the fixed flags
            self.assertGreater(compile_argv.index("-DFOO=1"), compile_argv.index("-static"))

    def test_compile_elf_raises_toolchain_missing_when_gcc_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._fake_compile(tmp)
            elf_out = tmp / "demo.elf"

            with mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=FileNotFoundError("riscv64-unknown-elf-gcc"),
            ):
                with self.assertRaises(ToolchainMissing):
                    compile_elf(src, elf_out)

    def test_compile_elf_raises_toolchain_missing_when_gcc_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._fake_compile(tmp)
            elf_out = tmp / "demo.elf"

            with mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["riscv64-unknown-elf-gcc"],
                    output="",
                    stderr="undefined reference to `main'",
                ),
            ):
                with self.assertRaises(ToolchainMissing):
                    compile_elf(src, elf_out)

    def test_compile_elf_raises_toolchain_missing_when_objdump_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._fake_compile(tmp)
            elf_out = tmp / "demo.elf"

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                if argv[0].endswith("-gcc"):
                    elf_out.write_bytes(b"stub")
                    return SimpleNamespace(stdout="", stderr="", returncode=0)
                raise FileNotFoundError(argv[0])

            with mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                with self.assertRaises(ToolchainMissing):
                    compile_elf(src, elf_out)


class EnsureSimulatorTest(unittest.TestCase):
    """Fake-subprocess coverage for :func:`ensure_simulator`."""

    def _layout_chipyard(self, tmp: Path, config_name: str) -> tuple[Path, Path]:
        sim_dir = tmp / "sims" / "verilator"
        sim_dir.mkdir(parents=True)
        simulator = sim_dir / f"simulator-chipyard.harness-{config_name}"
        return tmp, simulator

    def _which_stub(self, missing: set[str]):  # type: ignore[no-untyped-def]
        def fake_which(name: str) -> str | None:
            return None if name in missing else f"/usr/bin/{name}"

        return fake_which

    def test_ensure_simulator_builds_make_argv_and_returns_binary_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root, simulator = self._layout_chipyard(Path(tmp_str), "QChipRocketConfig")

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                self.assertEqual(argv[0], "make")
                self.assertEqual(argv[1], "-C")
                self.assertEqual(argv[2], str(chipyard_root / "sims" / "verilator"))
                self.assertEqual(argv[3], "CONFIG=QChipRocketConfig")
                simulator.write_bytes(b"stub simulator")
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing=set()),
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                result = ensure_simulator(chipyard_root, "QChipRocketConfig")

            self.assertEqual(result, simulator)
            self.assertTrue(result.is_file())

    def test_ensure_simulator_raises_toolchain_missing_when_tree_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            with self.assertRaises(ToolchainMissing):
                ensure_simulator(Path(tmp_str) / "does-not-exist", "QChipRocketConfig")

    def test_ensure_simulator_raises_toolchain_missing_when_gcc_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root, _ = self._layout_chipyard(Path(tmp_str), "QChipRocketConfig")
            with mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing={"riscv64-unknown-elf-gcc"}),
            ):
                with self.assertRaises(ToolchainMissing):
                    ensure_simulator(chipyard_root, "QChipRocketConfig")

    def test_ensure_simulator_raises_verilator_missing_when_verilator_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root, _ = self._layout_chipyard(Path(tmp_str), "QChipRocketConfig")
            with mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing={"verilator"}),
            ):
                with self.assertRaises(VerilatorMissing):
                    ensure_simulator(chipyard_root, "QChipRocketConfig")

    def test_ensure_simulator_raises_verilator_missing_when_build_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root, _ = self._layout_chipyard(Path(tmp_str), "QChipRocketConfig")

            with mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing=set()),
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    returncode=2,
                    cmd=["make"],
                    output="",
                    stderr="%Error-UNOPTFLAT",
                ),
            ):
                with self.assertRaises(VerilatorMissing):
                    ensure_simulator(chipyard_root, "QChipRocketConfig")

    def test_ensure_simulator_falls_back_to_glob_when_exact_name_missing(
        self,
    ) -> None:
        """simulator-chipyard-{config} (no '.harness' infix) is accepted."""

        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root = Path(tmp_str)
            sim_dir = chipyard_root / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            # Older-style name — the exact canonical path does NOT exist.
            legacy = sim_dir / "simulator-chipyard-QChipRocketConfig"

            def fake_run(*_, **__):  # type: ignore[no-untyped-def]
                legacy.write_bytes(b"stub")
                legacy.chmod(legacy.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing=set()),
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                result = ensure_simulator(chipyard_root, "QChipRocketConfig")

            self.assertEqual(result, legacy)
            self.assertTrue(os.access(result, os.X_OK))

    def test_ensure_simulator_exact_match_wins_over_glob_candidates(self) -> None:
        """When canonical name exists, glob fallback is not consulted."""

        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root, canonical = self._layout_chipyard(
                Path(tmp_str), "QChipRocketConfig"
            )
            sim_dir = canonical.parent
            # A glob-only candidate that should lose to the canonical name.
            rogue = sim_dir / "simulator-chipyard-QChipRocketConfig"

            def fake_run(*_, **__):  # type: ignore[no-untyped-def]
                canonical.write_bytes(b"canonical stub")
                canonical.chmod(canonical.stat().st_mode | stat.S_IEXEC)
                rogue.write_bytes(b"rogue stub")
                rogue.chmod(rogue.stat().st_mode | stat.S_IEXEC)
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing=set()),
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                result = ensure_simulator(chipyard_root, "QChipRocketConfig")

            self.assertEqual(result, canonical)

    def test_ensure_simulator_raises_when_no_candidate_is_executable(self) -> None:
        """Non-executable glob hits are rejected, preserving fail-fast behavior."""

        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root = Path(tmp_str)
            sim_dir = chipyard_root / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            not_executable = sim_dir / "simulator-chipyard-QChipRocketConfig"

            def fake_run(*_, **__):  # type: ignore[no-untyped-def]
                not_executable.write_bytes(b"stub")
                # Deliberately leave chmod 0o644 — not executable.
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing=set()),
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                with self.assertRaises(VerilatorMissing):
                    ensure_simulator(chipyard_root, "QChipRocketConfig")


class RunLocalSimTest(unittest.TestCase):
    """Fake-subprocess coverage for :func:`run_local_sim`."""

    def _fake_sim_stdout(self) -> str:
        # Build one real custom0 trace line using the shared encode helper so
        # ``filter_trace`` + ``parse_trace_text`` exercise the same regexes as
        # the archive pipeline in ``refresh_captures.sh``.
        q_set_word = pack_q_set(rs1=10, rs2=11)
        q_acquire_word = pack_q_acquire(rs1=12)
        return (
            "rocket startup banner\n"
            "INFO: booting chipyard harness\n"
            f"C0:       1050 [1] pc=[0000000080000378] W[r 0=0000000000000000][0] R[r10=0] R[r11=0] inst=[{q_set_word:08x}] unknown\n"
            "HYBRID,0,12,38,01,250000,40f00ab900370026\n"
            f"C0:       2400 [1] pc=[0000000080000380] W[r10=42][1] R[r12=0] R[r 0=0] inst=[{q_acquire_word:08x}] unknown\n"
            "- /.../TestDriver.v:158: Verilog $finish\n"
        )

    def test_run_local_sim_filters_trace_and_counts_custom0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            sim_dir = tmp / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            simulator = sim_dir / "simulator-chipyard.harness-QChipRocketConfig"
            simulator.write_bytes(b"fake simulator")
            elf = tmp / "hybrid_loop_demo.riscv"
            elf.write_bytes(b"fake elf")
            out_dir = tmp / "runs" / "local-1"

            fake_stdout = self._fake_sim_stdout()
            chipyard_output = sim_dir / "output" / "chipyard.harness.TestHarness.QChipRocketConfig"

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                self.assertEqual(argv[0], "make")
                self.assertIn("-C", argv)
                self.assertIn(str(sim_dir), argv)
                self.assertIn("run-binary", argv)
                self.assertIn("CONFIG=QChipRocketConfig", argv)
                self.assertIn(f"BINARY={elf.resolve()}", argv)
                # chipyard Makefile writes log + .out into the output subdir —
                # simulate that so the helper can copy them back.
                chipyard_output.mkdir(parents=True, exist_ok=True)
                (chipyard_output / "hybrid_loop_demo.log").write_text(fake_stdout, encoding="utf-8")
                (chipyard_output / "hybrid_loop_demo.out").write_text(fake_stdout, encoding="utf-8")
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                result = run_local_sim(
                    simulator,
                    elf,
                    out_dir,
                    chipyard_root=tmp,
                    config_name="QChipRocketConfig",
                )

            self.assertIsInstance(result, LocalRunResult)
            self.assertEqual(result.log_path, out_dir / "hybrid_loop_demo.log")
            self.assertEqual(result.trace_path, out_dir / "hybrid_loop_demo.trace.txt")
            self.assertTrue(result.log_path.is_file())
            self.assertTrue(result.trace_path.is_file())

            # Log mirrors the chipyard-produced UART log verbatim.
            self.assertEqual(result.log_path.read_text(encoding="utf-8"), fake_stdout)

            # Trace went through filter_trace — so HYBRID and INFO banners
            # are dropped, but the $finish marker and both custom0 lines survive.
            trace_text = result.trace_path.read_text(encoding="utf-8")
            self.assertNotIn("HYBRID,0,12", trace_text)
            self.assertNotIn("INFO: booting", trace_text)
            self.assertIn("Verilog $finish", trace_text)
            parsed = parse_trace_text(trace_text)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(result.custom0_count, 2)

            # cycle_count comes from the last parseable C<core>: cycle field.
            self.assertEqual(result.cycle_count, 2400)

            self.assertEqual(result.trace_bytes, result.trace_path.stat().st_size)
            self.assertEqual(result.log_bytes, result.log_path.stat().st_size)
            self.assertGreaterEqual(result.wall_seconds, 0.0)

    def test_run_local_sim_raises_verilator_missing_when_binary_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            sim_dir = tmp / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            simulator = sim_dir / "simulator-chipyard.harness-QChipRocketConfig"
            # Create the simulator file so the new pre-flight check passes;
            # the stubbed subprocess.run still raises FileNotFoundError on make.
            simulator.write_bytes(b"fake simulator")
            elf = tmp / "demo.elf"
            elf.write_bytes(b"fake elf")
            out_dir = tmp / "runs"

            with mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=FileNotFoundError("make"),
            ):
                with self.assertRaises(VerilatorMissing):
                    run_local_sim(
                        simulator,
                        elf,
                        out_dir,
                        chipyard_root=tmp,
                        config_name="QChipRocketConfig",
                    )

    def test_run_local_sim_raises_verilator_missing_when_simulator_path_absent(
        self,
    ) -> None:
        # New pre-flight check: caller's simulator path doesn't exist at all.
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            sim_dir = tmp / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            simulator = sim_dir / "simulator-chipyard.harness-QChipRocketConfig"
            # Intentionally do NOT create simulator.
            elf = tmp / "demo.elf"
            elf.write_bytes(b"fake elf")
            out_dir = tmp / "runs"

            with self.assertRaises(VerilatorMissing):
                run_local_sim(
                    simulator,
                    elf,
                    out_dir,
                    chipyard_root=tmp,
                    config_name="QChipRocketConfig",
                )


if __name__ == "__main__":
    unittest.main()
