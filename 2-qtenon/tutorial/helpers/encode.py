"""Helpers for packing and decoding tutorial-relevant custom0 RoCC instructions."""

from __future__ import annotations

from dataclasses import dataclass

CUSTOM0_OPCODE = 0b0001011

COMMAND_FUNCT7 = {
    "q_set": 0,
    "q_update": 1,
    "q_run": 4,
    "q_gen": 5,
    "q_acquire": 6,
}


@dataclass(frozen=True)
class CommandSpec:
    """Static encoding metadata for a tutorial-visible custom0 command."""

    name: str
    funct3: int
    funct7: int
    rd: int = 0


ENCODING_SPECS = {
    "q_set": CommandSpec("q_set", funct3=0b011, funct7=COMMAND_FUNCT7["q_set"]),
    "q_update": CommandSpec("q_update", funct3=0b011, funct7=COMMAND_FUNCT7["q_update"]),
    "q_run": CommandSpec("q_run", funct3=0b110, funct7=COMMAND_FUNCT7["q_run"]),
    "q_gen": CommandSpec("q_gen", funct3=0b000, funct7=COMMAND_FUNCT7["q_gen"]),
    "q_acquire": CommandSpec("q_acquire", funct3=0b110, funct7=COMMAND_FUNCT7["q_acquire"], rd=10),
}


def normalize_register(register: int | str) -> int:
    """Accept `x11` or `11` and return the numeric register index."""

    if isinstance(register, str):
        if not register.startswith("x"):
            raise ValueError(f"Register names must look like `xN`, got {register!r}.")
        register = int(register[1:])

    register = int(register)
    if not 0 <= register <= 31:
        raise ValueError(f"Register index must be in [0, 31], got {register}.")
    return register


def pack_r_type(*, opcode: int, funct3: int, funct7: int, rd: int, rs1: int, rs2: int) -> int:
    """Pack a raw R-type instruction word."""

    rd = normalize_register(rd)
    rs1 = normalize_register(rs1)
    rs2 = normalize_register(rs2)
    if not 0 <= funct3 <= 0b111:
        raise ValueError(f"funct3 must be a 3-bit value, got {funct3}.")
    if not 0 <= funct7 <= 0b1111111:
        raise ValueError(f"funct7 must be a 7-bit value, got {funct7}.")

    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def pack_command(command: str, *, rs1: int = 0, rs2: int = 0, rd: int | None = None) -> int:
    """Pack a tutorial-visible command for comparison with decoded traces."""

    spec = ENCODING_SPECS[command]
    return pack_r_type(
        opcode=CUSTOM0_OPCODE,
        funct3=spec.funct3,
        funct7=spec.funct7,
        rd=spec.rd if rd is None else rd,
        rs1=rs1,
        rs2=rs2,
    )


def pack_q_set(rs1: int, rs2: int, *, rd: int = 0) -> int:
    """Pack the instruction emitted by `q_set(rs1, rs2)` in `rocc.h`."""

    return pack_command("q_set", rs1=rs1, rs2=rs2, rd=rd)


def pack_q_update(rs1: int, rs2: int, *, rd: int = 0) -> int:
    """Pack the instruction emitted by `q_update(rs1, rs2)` in `rocc.h`."""

    return pack_command("q_update", rs1=rs1, rs2=rs2, rd=rd)


def pack_q_run(rs1: int, *, rd: int = 0) -> int:
    """Pack the instruction emitted by `q_run(rs1)` in `rocc.h`."""

    return pack_command("q_run", rs1=rs1, rs2=0, rd=rd)


def pack_q_gen(*, rd: int = 0) -> int:
    """Pack the instruction emitted by `q_gen()` in `rocc.h`."""

    return pack_command("q_gen", rs1=0, rs2=0, rd=rd)


def pack_q_acquire(rs1: int, *, rd: int = 10) -> int:
    """Pack the instruction emitted by `q_acquire(rd, rs1)` in `rocc.h`."""

    return pack_command("q_acquire", rs1=rs1, rs2=0, rd=rd)


def decode_instruction(word: int) -> dict[str, int]:
    """Decode a 32-bit RISC-V word into the fields we need for tutorial analysis."""

    word &= 0xFFFFFFFF
    return {
        "opcode": word & 0x7F,
        "rd": (word >> 7) & 0x1F,
        "funct3": (word >> 12) & 0x7,
        "rs1": (word >> 15) & 0x1F,
        "rs2": (word >> 20) & 0x1F,
        "funct7": (word >> 25) & 0x7F,
    }


def identify_command(decoded: dict[str, int]) -> str | None:
    """Return the known command name for a decoded instruction, if any."""

    for name, spec in ENCODING_SPECS.items():
        if decoded["opcode"] == CUSTOM0_OPCODE and decoded["funct3"] == spec.funct3 and decoded["funct7"] == spec.funct7:
            return name
    if decoded["opcode"] == CUSTOM0_OPCODE and decoded["funct7"] == COMMAND_FUNCT7["q_run"]:
        return "q_run"
    return None
