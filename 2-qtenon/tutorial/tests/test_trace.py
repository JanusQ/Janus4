"""Unit tests for shared trace helpers (filter + path classification + split)."""

from __future__ import annotations

import unittest
from pathlib import Path

from tutorial.helpers.encode import pack_q_acquire, pack_q_gen, pack_q_run, pack_q_set, pack_q_update
from tutorial.helpers.trace import (
    classify_path,
    filter_trace,
    last_trace_cycle,
    parse_acquire_completion_waits,
    parse_trace_text,
    split_hybrid_iterations,
)

CAPTURE_TRACE = (
    Path(__file__).resolve().parents[1]
    / "captures"
    / "hybrid_loop"
    / "hybrid_loop.trace.txt"
)


def _trace_line(cycle: int, pc: int, word: int) -> str:
    """Build a Rocket-chip-flavoured retire line that carries a 32-bit word."""

    return f"C0:{cycle:>10} [1] pc=[{pc:016x}] W[r10=0000000000000000][1] inst=[{word:08x}] DASM(custom0)"


def _host_retire_line(cycle: int, pc: int, word: int = 0x00008067) -> str:
    """Build an ordinary host retire line that should not decode as custom0."""

    return f"C0:{cycle:>10} [1] pc=[{pc:016x}] W[r 0=0000000000000000][0] inst=[{word:08x}] DASM(ret)"


class FilterTraceTest(unittest.TestCase):
    def test_keeps_instruction_and_finish_lines(self) -> None:
        q_set_word = pack_q_set(10, 11)
        q_gen_word = pack_q_gen()
        lines = [
            "some noisy startup line with no instruction",
            _trace_line(100, 0x80001000, q_set_word),
            "zero-jump trap handler noise",
            _trace_line(120, 0x80001004, q_gen_word),
            "   - Verilog $finish executed at simulation time 123ns",
            "",
        ]

        out = filter_trace("\n".join(lines))
        kept = out.splitlines()

        self.assertEqual(len(kept), 3)
        self.assertIn(f"inst=[{q_set_word:08x}]", kept[0])
        self.assertIn(f"inst=[{q_gen_word:08x}]", kept[1])
        self.assertIn("Verilog $finish", kept[2])
        # filter_trace always terminates non-empty output with a trailing newline
        self.assertTrue(out.endswith("\n"))

    def test_empty_input_returns_empty_string(self) -> None:
        self.assertEqual(filter_trace(""), "")
        self.assertEqual(filter_trace("no matches at all\nnothing interesting\n"), "")

    def test_preserves_original_order(self) -> None:
        first = _trace_line(10, 0x1000, pack_q_update(10, 11))
        second = _trace_line(20, 0x1004, pack_q_acquire(11, rd=10))
        resume = _host_retire_line(1150, 0x1008)
        text = "\n".join(
            ["junk", first, "more junk", second, "noise", resume, "Verilog $finish: done"]
        )

        kept = filter_trace(text).splitlines()

        self.assertEqual(kept, [first, second, resume, "Verilog $finish: done"])

    def test_keeps_only_first_resume_after_acquire(self) -> None:
        acquire = _trace_line(20, 0x1004, pack_q_acquire(11, rd=10))
        first_resume = _host_retire_line(1150, 0x1008)
        second_resume = _host_retire_line(1151, 0x100c)
        text = "\n".join([acquire, first_resume, second_resume])

        kept = filter_trace(text).splitlines()

        self.assertEqual(kept, [acquire, first_resume])


class ClassifyPathTest(unittest.TestCase):
    def test_known_commands(self) -> None:
        self.assertEqual(classify_path("q_update"), "①")
        self.assertEqual(classify_path("q_set"), "②")
        self.assertEqual(classify_path("q_acquire"), "②")
        self.assertEqual(classify_path("q_gen"), "—")
        self.assertEqual(classify_path("q_run"), "—")

    def test_unknown_and_none_default_to_dash(self) -> None:
        self.assertEqual(classify_path(None), "—")
        self.assertEqual(classify_path("unknown_op"), "—")
        self.assertEqual(classify_path(""), "—")


class SplitHybridIterationsTest(unittest.TestCase):
    def test_real_capture_yields_four_iterations_of_four(self) -> None:
        self.assertTrue(
            CAPTURE_TRACE.exists(),
            f"expected capture archive at {CAPTURE_TRACE}",
        )
        parsed = parse_trace_text(CAPTURE_TRACE.read_text(encoding="utf-8"))

        iterations = split_hybrid_iterations(parsed)

        self.assertEqual(len(iterations), 4)
        for idx, iteration in enumerate(iterations):
            with self.subTest(iteration=idx):
                self.assertEqual(len(iteration), 4)
                self.assertIn(iteration[0].command, {"q_set", "q_update"})
                self.assertEqual(iteration[-1].command, "q_acquire")
        # First iter must start from the warm-up q_set; the remaining three
        # iterations run the update/gen/run/acquire path.
        self.assertEqual(iterations[0][0].command, "q_set")
        for tail in iterations[1:]:
            self.assertEqual(tail[0].command, "q_update")

    def test_real_capture_has_acquire_completion_waits(self) -> None:
        trace_text = CAPTURE_TRACE.read_text(encoding="utf-8")

        waits = parse_acquire_completion_waits(trace_text)

        self.assertEqual(len(waits), 4)
        self.assertEqual([wait.iteration for wait in waits], [0, 1, 2, 3])
        for wait in waits:
            with self.subTest(iteration=wait.iteration):
                self.assertGreater(wait.acquire_to_resume_cycles, 0)
                self.assertIsNotNone(wait.gen_to_resume_cycles)
                self.assertGreater(wait.gen_to_resume_cycles, wait.acquire_to_resume_cycles)
        last_cycle = last_trace_cycle(trace_text)
        self.assertIsNotNone(last_cycle)
        self.assertGreaterEqual(last_cycle, waits[-1].resume_cycle)


class AcquireCompletionWaitTest(unittest.TestCase):
    def test_parse_waits_pairs_acquire_with_following_host_retire(self) -> None:
        text = "\n".join(
            [
                _trace_line(100, 0x2000, pack_q_set(10, 11)),
                _trace_line(104, 0x2004, pack_q_gen()),
                _trace_line(105, 0x2008, pack_q_run(12)),
                _trace_line(110, 0x200c, pack_q_acquire(11, rd=10)),
                _host_retire_line(1240, 0x2010),
            ]
        )

        waits = parse_acquire_completion_waits(text)

        self.assertEqual(len(waits), 1)
        self.assertEqual(waits[0].iteration, 0)
        self.assertEqual(waits[0].acquire_to_resume_cycles, 1130)
        self.assertEqual(waits[0].gen_to_resume_cycles, 1136)
        self.assertEqual(waits[0].run_to_resume_cycles, 1135)


if __name__ == "__main__":
    unittest.main()
