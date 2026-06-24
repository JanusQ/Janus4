"""Unit tests for custom0 instruction packing and decoding."""

from __future__ import annotations

import unittest

from tutorial.helpers.encode import (
    decode_instruction,
    identify_command,
    pack_r_type,
    pack_q_acquire,
    pack_q_gen,
    pack_q_run,
    pack_q_set,
    pack_q_update,
)


class EncodeTest(unittest.TestCase):
    def test_pack_q_set_matches_expected_word(self) -> None:
        word = pack_q_set(10, 11)
        self.assertEqual(word, 0x00B5300B)
        self.assertEqual(identify_command(decode_instruction(word)), "q_set")

    def test_q_update_roundtrip(self) -> None:
        update = decode_instruction(pack_q_update(10, 11))
        self.assertEqual(update["funct7"], 1)
        self.assertEqual(update["funct3"], 0b011)

    def test_q_run_and_q_gen_roundtrip(self) -> None:
        run = decode_instruction(pack_q_run(11))
        q_gen = decode_instruction(pack_q_gen())
        self.assertEqual(run["funct7"], 4)
        self.assertEqual(run["funct3"], 0b110)
        self.assertEqual(q_gen["funct7"], 5)
        self.assertEqual(q_gen["funct3"], 0)

    def test_legacy_q_run_funct3_is_identified(self) -> None:
        legacy_run = decode_instruction(
            pack_r_type(opcode=0b0001011, funct3=0b011, funct7=4, rd=0, rs1=11, rs2=12)
        )

        self.assertEqual(identify_command(legacy_run), "q_run")

    def test_q_acquire_roundtrip(self) -> None:
        acquire = decode_instruction(pack_q_acquire(11, rd=10))
        self.assertEqual(acquire["funct7"], 6)
        self.assertEqual(acquire["funct3"], 0b110)
        self.assertEqual(acquire["rd"], 10)


if __name__ == "__main__":
    unittest.main()
