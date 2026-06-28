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

    The Phase 2 Docker image bakes in ``QTENON_RISCV_GCC`` and
    ``QTENON_SIMULATOR``; the per-test env-var scrub in :meth:`setUp` keeps
    the default-path tests hermetic when run inside that image so AC5
    (`unittest` passes inside container) holds.
    """

    def setUp(self) -> None:
        self._env_patcher = mock.patch.dict(
            "tutorial.helpers.local_run.os.environ",
            {
                k: v
                for k, v in os.environ.items()
                if k not in {"QTENON_RISCV_GCC", "QTENON_SIMULATOR"}
            },
            clear=True,
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)

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

    def test_compile_elf_honors_qtenon_riscv_gcc_env_var(self) -> None:
        """Phase 2: ``QTENON_RISCV_GCC`` overrides the PATH-relative default
        so the Docker image can pin ``/usr/bin/riscv64-unknown-elf-gcc``
        without callers caring."""

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._fake_compile(tmp)
            elf_out = tmp / "demo.elf"
            pinned_gcc = "/opt/riscv/bin/riscv64-unknown-elf-gcc"

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                if argv[0].endswith("-gcc"):
                    elf_out.write_bytes(b"stub")
                    return SimpleNamespace(stdout="", stderr="", returncode=0)
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                {"QTENON_RISCV_GCC": pinned_gcc},
                clear=False,
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ) as patched:
                compile_elf(src, elf_out)

            compile_argv = patched.call_args_list[0].args[0]
            self.assertEqual(compile_argv[0], pinned_gcc)
            # Derived objdump path also follows the env-var prefix.
            objdump_argv = patched.call_args_list[1].args[0]
            self.assertEqual(objdump_argv[0], "/opt/riscv/bin/riscv64-unknown-elf-objdump")

    def test_compile_elf_falls_back_to_path_when_env_var_unset(self) -> None:
        """Default behavior is preserved when ``QTENON_RISCV_GCC`` is unset."""

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            src = self._fake_compile(tmp)
            elf_out = tmp / "demo.elf"

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                if argv[0].endswith("-gcc"):
                    elf_out.write_bytes(b"stub")
                    return SimpleNamespace(stdout="", stderr="", returncode=0)
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            # Drop QTENON_RISCV_GCC if it leaked in from the host shell.
            scrubbed = {
                k: v
                for k, v in os.environ.items()
                if k != "QTENON_RISCV_GCC"
            }
            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                scrubbed,
                clear=True,
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ) as patched:
                compile_elf(src, elf_out)

            compile_argv = patched.call_args_list[0].args[0]
            self.assertEqual(compile_argv[0], "riscv64-unknown-elf-gcc")


class EnsureSimulatorTest(unittest.TestCase):
    """Fake-subprocess coverage for :func:`ensure_simulator`."""

    def setUp(self) -> None:
        # Same env-var scrub as CompileElfTest — keep the default-path tests
        # hermetic inside the Phase 2 Docker image (which bakes in
        # ``QTENON_RISCV_GCC`` / ``QTENON_SIMULATOR``).
        self._env_patcher = mock.patch.dict(
            "tutorial.helpers.local_run.os.environ",
            {
                k: v
                for k, v in os.environ.items()
                if k not in {"QTENON_RISCV_GCC", "QTENON_SIMULATOR"}
            },
            clear=True,
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)

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

            def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
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

            def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
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

            def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
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

    def test_ensure_simulator_returns_env_var_path_when_executable(self) -> None:
        """Phase 2: ``QTENON_SIMULATOR`` short-circuits the Chipyard tree
        walk when it points at an executable file. Used by Phase 3 to
        bind the bundled ``/usr/local/bin/qtenon-sim`` directly."""

        with tempfile.NamedTemporaryFile(
            prefix="qtenon-sim-", delete=False
        ) as tmp_bin:
            sim_path = Path(tmp_bin.name)
            tmp_bin.write(b"#!/bin/sh\nexit 0\n")
        try:
            sim_path.chmod(
                sim_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
            )

            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                {"QTENON_SIMULATOR": str(sim_path)},
                clear=False,
            ):
                # chipyard_root is intentionally a bogus path — env-var hit
                # must skip the tree walk entirely.
                result = ensure_simulator(
                    Path("missing-chipyard-root"),
                    "QChipRocketConfig",
                )

            self.assertEqual(result, sim_path)
        finally:
            sim_path.unlink(missing_ok=True)

    def test_ensure_simulator_falls_back_when_env_var_path_missing(self) -> None:
        """If ``QTENON_SIMULATOR`` is set but the file does not exist (or is
        not executable), the helper falls through to the Chipyard tree
        walk so a misconfigured env var doesn't silently mask setup issues."""

        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root, simulator = self._layout_chipyard(
                Path(tmp_str), "QChipRocketConfig"
            )

            def fake_run(_argv, **_):  # type: ignore[no-untyped-def]
                simulator.write_bytes(b"stub simulator")
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                {"QTENON_SIMULATOR": "/this/path/does/not/exist/qtenon-sim"},
                clear=False,
            ), mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing=set()),
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                result = ensure_simulator(chipyard_root, "QChipRocketConfig")

            # Fell back to the chipyard-built canonical simulator.
            self.assertEqual(result, simulator)

    def test_ensure_simulator_falls_back_when_env_var_unset(self) -> None:
        """Existing behavior preserved when ``QTENON_SIMULATOR`` is unset."""

        with tempfile.TemporaryDirectory() as tmp_str:
            chipyard_root, simulator = self._layout_chipyard(
                Path(tmp_str), "QChipRocketConfig"
            )

            def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
                simulator.write_bytes(b"stub simulator")
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            scrubbed = {
                k: v
                for k, v in os.environ.items()
                if k != "QTENON_SIMULATOR"
            }
            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                scrubbed,
                clear=True,
            ), mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                side_effect=self._which_stub(missing=set()),
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                result = ensure_simulator(chipyard_root, "QChipRocketConfig")

            self.assertEqual(result, simulator)


class RunLocalSimTest(unittest.TestCase):
    """Fake-subprocess coverage for :func:`run_local_sim`."""

    def _fake_sim_stdout(self) -> str:
        # Build one real custom0 trace line using the shared encode helper so
        # ``filter_trace`` + ``parse_trace_text`` exercise the same regexes as
        # the archive pipeline.
        q_set_word = pack_q_set(rs1=10, rs2=11)
        q_acquire_word = pack_q_acquire(rs1=12)
        return (
            "rocket startup banner\n"
            "INFO: booting chipyard harness\n"
            f"C0:       1050 [1] pc=[0000000080000378] W[r 0=0000000000000000][0] R[r10=0] R[r11=0] inst=[{q_set_word:08x}] unknown\n"
            "HYBRID,0,12,38,01,250000,40f00ab900370026\n"
            f"C0:       2400 [1] pc=[0000000080000380] W[r10=42][1] R[r12=0] R[r 0=0] inst=[{q_acquire_word:08x}] unknown\n"
            "C0:       2500 [1] pc=[0000000080000384] W[r 0=0][0] R[r 1=0] R[r 0=0] inst=[00008067] ret\n"
            "- /.../TestDriver.v:158: Verilog $finish\n"
        )

    def test_run_local_sim_filters_trace_and_counts_custom0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            sim_dir = tmp / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            # Make-mode preconditions: a Makefile must exist for
            # _direct_mode_available to return False; the test environment
            # also needs ``make`` on PATH (CI runners ship it).
            (sim_dir / "Makefile").write_text("# stub\n", encoding="utf-8")
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

            # Force make-mode by stubbing the QTENON_DIRECT_SIM env var off
            # and ensuring shutil.which("make") returns a path so the
            # direct-mode pre-flight returns False.
            scrubbed_env = {
                k: v for k, v in os.environ.items() if k != "QTENON_DIRECT_SIM"
            }
            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                scrubbed_env,
                clear=True,
            ), mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                return_value="/usr/bin/make",
            ), mock.patch(
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
            self.assertIn("inst=[00008067]", trace_text)
            parsed = parse_trace_text(trace_text)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(result.custom0_count, 2)

            # cycle_count comes from the last parseable C<core>: cycle field.
            self.assertEqual(result.cycle_count, 2500)

            self.assertEqual(result.trace_bytes, result.trace_path.stat().st_size)
            self.assertEqual(result.log_bytes, result.log_path.stat().st_size)
            self.assertGreaterEqual(result.wall_seconds, 0.0)

    def test_run_local_sim_fast_mode_does_not_require_instruction_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            sim_dir = tmp / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            (sim_dir / "Makefile").write_text("# stub\n", encoding="utf-8")
            simulator = sim_dir / "simulator-chipyard.harness-QChipRocketConfig"
            simulator.write_bytes(b"fake simulator")
            elf = tmp / "paper_vqe_spsa.riscv"
            elf.write_bytes(b"fake elf")
            out_dir = tmp / "runs" / "paper"
            chipyard_output = sim_dir / "output" / "chipyard.harness.TestHarness.QChipRocketConfig"

            def fake_run(argv, **_):  # type: ignore[no-untyped-def]
                self.assertIn("run-binary-fast", argv)
                self.assertIn("SIM_FLAGS=+max-cycles=30000000", argv)
                chipyard_output.mkdir(parents=True, exist_ok=True)
                (chipyard_output / "paper_vqe_spsa.log").write_text(
                    "paper_vqe_spsa,v3\n",
                    encoding="utf-8",
                )
                return SimpleNamespace(stdout="", stderr="", returncode=0)

            scrubbed_env = {
                k: v for k, v in os.environ.items() if k != "QTENON_DIRECT_SIM"
            }
            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                scrubbed_env,
                clear=True,
            ), mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                return_value="/usr/bin/make",
            ), mock.patch(
                "tutorial.helpers.local_run.subprocess.run",
                side_effect=fake_run,
            ):
                result = run_local_sim(
                    simulator,
                    elf,
                    out_dir,
                    chipyard_root=tmp,
                    config_name="QChipRocketConfig",
                    fast=True,
                    sim_flags=["+max-cycles=30000000"],
                )

            trace_text = result.trace_path.read_text(encoding="utf-8")
            self.assertIn("instruction trace omitted", trace_text)
            self.assertEqual(result.custom0_count, 0)
            self.assertEqual(result.cycle_count, 0)

    def test_run_local_sim_raises_verilator_missing_when_binary_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            sim_dir = tmp / "sims" / "verilator"
            sim_dir.mkdir(parents=True)
            # Make-mode preconditions: keep this test exercising the make-mode
            # branch so the FileNotFoundError on make surfaces as VerilatorMissing.
            (sim_dir / "Makefile").write_text("# stub\n", encoding="utf-8")
            simulator = sim_dir / "simulator-chipyard.harness-QChipRocketConfig"
            # Create the simulator file so the new pre-flight check passes;
            # the stubbed subprocess.run still raises FileNotFoundError on make.
            simulator.write_bytes(b"fake simulator")
            elf = tmp / "demo.elf"
            elf.write_bytes(b"fake elf")
            out_dir = tmp / "runs"

            scrubbed_env = {
                k: v for k, v in os.environ.items() if k != "QTENON_DIRECT_SIM"
            }
            with mock.patch.dict(
                "tutorial.helpers.local_run.os.environ",
                scrubbed_env,
                clear=True,
            ), mock.patch(
                "tutorial.helpers.local_run.shutil.which",
                return_value="/usr/bin/make",
            ), mock.patch(
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

    def test_run_local_sim_direct_mode_uses_simulator_directly(self) -> None:
        """Phase 3 v2: ``QTENON_DIRECT_SIM=1`` skips the chipyard make tree
        and invokes the simulator binary directly. The fake sim emits a
        captured chisel-printf trace on stderr (16 lines from the hybrid_loop
        capture) and the captured UART log on stdout, mirroring how the real
        chipyard simulator separates trace (stderr) from log (stdout)."""

        # 16 chipyard chisel-printf lines, verbatim from
        # code/tutorial/captures/hybrid_loop/hybrid_loop.trace.txt.
        captured_trace_lines = [
            "C0:      20060 [1] pc=[0000000080000378] W[r 0=0000000000000000][0] R[r12=00000000800021b0] R[r15=0000400000000000] inst=[00f6300b] unknown",
            "C0:      20064 [1] pc=[00000000800002ba] W[r 0=0000000000000000][0] R[r 0=0000000000000000] R[r 0=0000000000000000] inst=[0a00000b] unknown",
            "C0:      20083 [1] pc=[00000000800002be] W[r 0=0000000000000000][0] R[r24=0000000000000080] R[r 0=0000000000000000] inst=[080c600b] unknown",
            "C0:      20235 [1] pc=[00000000800002c6] W[r10=0000000000000000][0] R[r11=0000000080002170] R[r 0=0000000000000000] inst=[0c05e50b] unknown",
            "C0:      31683 [1] pc=[00000000800002b2] W[r 0=0000000000000000][0] R[r15=a101000100260013] R[r14=0000000000000040] inst=[02e7b00b] unknown",
            "C0:      31685 [1] pc=[00000000800002ba] W[r 0=0000000000000000][0] R[r 0=0000000000000000] R[r 0=0000000000000000] inst=[0a00000b] unknown",
            "C0:      31686 [1] pc=[00000000800002be] W[r 0=0000000000000000][0] R[r24=0000000000000080] R[r 0=0000000000000000] inst=[080c600b] unknown",
            "C0:      31688 [1] pc=[00000000800002c6] W[r10=0000000000000000][0] R[r11=0000000080002170] R[r 0=0000000000000000] inst=[0c05e50b] unknown",
            "C0:      42660 [1] pc=[00000000800002b2] W[r 0=0000000000000000][0] R[r15=a102000200370013] R[r14=0000000000000040] inst=[02e7b00b] unknown",
            "C0:      42662 [1] pc=[00000000800002ba] W[r 0=0000000000000000][0] R[r 0=0000000000000000] R[r 0=0000000000000000] inst=[0a00000b] unknown",
            "C0:      42663 [1] pc=[00000000800002be] W[r 0=0000000000000000][0] R[r24=0000000000000080] R[r 0=0000000000000000] inst=[080c600b] unknown",
            "C0:      42665 [1] pc=[00000000800002c6] W[r10=0000000000000000][0] R[r11=0000000080002170] R[r 0=0000000000000000] inst=[0c05e50b] unknown",
            "C0:      53635 [1] pc=[00000000800002b2] W[r 0=0000000000000000][0] R[r15=a103000300370026] R[r14=0000000000000040] inst=[02e7b00b] unknown",
            "C0:      53637 [1] pc=[00000000800002ba] W[r 0=0000000000000000][0] R[r 0=0000000000000000] R[r 0=0000000000000000] inst=[0a00000b] unknown",
            "C0:      53638 [1] pc=[00000000800002be] W[r 0=0000000000000000][0] R[r24=0000000000000080] R[r 0=0000000000000000] inst=[080c600b] unknown",
            "C0:      53640 [1] pc=[00000000800002c6] W[r10=0000000000000000][0] R[r11=0000000080002170] R[r 0=0000000000000000] inst=[0c05e50b] unknown",
            "C0:      54773 [1] pc=[00000000800002ca] W[r 0=0000000000000000][0] R[r 1=00000000800002ca] R[r 0=0000000000000000] inst=[00008067] ret",
        ]
        captured_log = (
            "[UART] UART0 is here (stdin/stdout).\n"
            "mode=Act 3 minimal hardware loop\n"
            "iter,theta0_idx,theta1_idx,sample_bits,objective_ppm,acquire_word\n"
            "0,12,38,01,1295,4616195180039897100\n"
            "- simulator/verilator/generated-src/X.v:158: Verilog $finish\n"
        )

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            simulator = tmp / "fake-sim"
            # Build a tiny Python script that replays the captured trace on
            # stderr and the captured log on stdout, then exits 0. Using
            # repr() embeds the strings safely without needing escape gymnastics.
            trace_payload = "\n".join(captured_trace_lines) + "\n"
            simulator.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                f"sys.stdout.write({captured_log!r})\n"
                f"sys.stderr.write({trace_payload!r})\n",
                encoding="utf-8",
            )
            simulator.chmod(
                simulator.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
            )

            elf = tmp / "hybrid_loop_demo.riscv"
            elf.write_bytes(b"fake elf")
            out_dir = tmp / "runs" / "direct-1"

            os.environ["QTENON_DIRECT_SIM"] = "1"
            try:
                # chipyard_root intentionally bogus — direct-mode pre-flight
                # short-circuits the make tree walk.
                result = run_local_sim(
                    simulator,
                    elf,
                    out_dir,
                    chipyard_root=Path("missing-chipyard-root"),
                    config_name="QChipRocketConfig",
                )
            finally:
                os.environ.pop("QTENON_DIRECT_SIM", None)

            self.assertIsInstance(result, LocalRunResult)
            self.assertGreater(result.trace_bytes, 0)
            self.assertEqual(result.custom0_count, 16)
            self.assertGreater(result.cycle_count, 0)
            self.assertEqual(result.cycle_count, 54773)
            # Log should mirror stdout verbatim.
            self.assertEqual(result.log_path.read_text(encoding="utf-8"), captured_log)

    def tearDown(self) -> None:
        os.environ.pop("QTENON_DIRECT_SIM", None)


if __name__ == "__main__":
    unittest.main()
