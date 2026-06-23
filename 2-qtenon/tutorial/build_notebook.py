"""Generate the Qtenon tutorial notebook from v3 18-cell layout.

Cell list follows `.trellis/tasks/04-21-qtenon-demo-rewrite/cell_specs.md`
(v3, 9 markdown + 9 code). This generator writes the cell templates only;
cell templates may reference helpers that live in demo-rewrite's future
patch (Option A). `nbconvert --execute` is intentionally not expected to
succeed here until that helper work lands.
"""

from __future__ import annotations

import json
from pathlib import Path


# ----- cell constructors -----------------------------------------------------


def markdown_cell(source: str, *, cell_id: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {},
        "source": source.strip() + "\n",
    }


def code_cell(source: str, *, cell_id: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "id": cell_id,
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.strip() + "\n",
    }


# ----- markdown bodies (frozen except cell [2]) ------------------------------


MD_WHY_QTENON = """
# Qtenon Tutorial: Hybrid Quantum-Classical as One RISC-V Program

This notebook is the hands-on companion to the Qtenon section of the Janus 4.0 tutorial. Every cell is meant to be read alongside the corresponding slide; the story is the shift from a decoupled host + FPGA-controller + quantum architecture to a tightly coupled RISC-V core whose ISA treats quantum programs as computable data.

The paper claim we are servicing: end-to-end hybrid workloads run up to 14.9× faster than state-of-the-art decoupled architectures (Qtenon, ISCA 2025). This notebook does not reproduce that speedup number. It reproduces the mechanisms that produce it, at a scale small enough to run entirely on the local machine in under a minute.

## Why Qtenon exists

A hybrid quantum-classical algorithm spends most of its wall-clock time **not** in quantum computation. Figure 1 of the paper (reproduced below) shows the profile for 64-qubit QAOA, VQE, and QNN: quantum execution is 7.9 %–11 % of the total; the rest is communication between host and quantum accelerator, repeated classical compilation, and classical post-processing.

![Runtime breakdown for hybrid workloads, paper Fig. 1](figures/time_percentage.svg)

The root cause is architectural: today's systems put a decoupled FPGA controller between the host CPU and the quantum device, with a USB or Ethernet link carrying every circuit and every measurement across a process boundary. Qtenon replaces that middleman with a RoCC-attached quantum controller sitting at the host's L1 cache level.

|  | Decoupled (eQASM, HiSEP-Q) | **Qtenon** |
| --- | --- | --- |
| Communication latency | 1–10 ms (USB/Ethernet) | **10–100 ns** (RoCC + TileLink) |
| Instruction count (64-qubit QAOA) | ~3×10⁴ | **~285** |
| Recompilation overhead | 1–100 ms | **10–100 ns** |
| Execution model | Sequential | **Interleaved** |

*(Table 1 of the paper, §3.)*

The rest of this notebook turns each row of that table into code you can read and cycle counts you can check.

![Qtenon system overview, paper Fig. 2](figures/qtenon_overview.svg)
"""


MD_SETUP_V3 = """
## Setup: verify toolchain, compile the hybrid loop ELF

The rest of this notebook is driven by a single program,
`software/tests/hybrid_loop_demo.c`, and by a Verilator build of
`QChipRocketConfig`. The tutorial container ships the RISC-V
toolchain (`riscv64-unknown-elf-gcc`), the Verilator binary, and
the chipyard source tree, so the next cell does two things right
here in the container:

1. cross-compile the C program to a RISC-V ELF,
2. make sure the Verilator simulator binary is up to date.

If the image already has the binary, step 2 is a no-op and takes
a few seconds. A full rebuild takes ~1 min on 8–16 cores.

**The simulator is not invoked yet.** That lands at the bottom of
the notebook, at the opening of §End-to-end consequence, where we
actually run all four iterations of the hybrid loop and walk the
retire timeline in one pass. The middle sections (programming
model, R-type field layout, two on-chip datapaths) draw their
evidence from the checked-in `captures/hybrid_loop/` archive: same
bytes, same cycles, same custom0 words the live run will produce
at the bottom. That ordering keeps the story on a crescendo. We
first unpack what every single instruction means statically. Then,
at the end, we run the loop live and see the 16 retires land in
order.
"""


MD_PROGRAMMING_MODEL = """
## Programming model: the hybrid loop as one RISC-V program

In a decoupled system, a hybrid iteration looks like this (pseudocode for the classic Janus 3.0 world):

```python
# Host Python process
circuit  = build_circuit(theta)
compiled = compile_to_eqasm(circuit)          # 1–100 ms
driver.submit(compiled)                       # 1–10 ms over Ethernet
result   = driver.wait_for_result()           # blocks host
theta    = classical_update(result)           # then host works
```

Every quantum-host round trip crosses a process boundary and a network link. Compilation restarts every iteration because the FPGA controller has no primitive for "the program is the same, just update parameter θ".

Qtenon replaces that with a RoCC ISA extension. Five instructions, shown below, are all emitted inline by a single C compiler:

| Class | Instruction | What it does |
| --- | --- | --- |
| Data communication | `q_update` | Host register → Quantum Controller Cache (small, 64-bit) |
|  | `q_set` | Host memory → Quantum Controller Cache (bulk) |
|  | `q_acquire` | Quantum Controller Cache → Host memory (bulk) |
| Computation | `q_gen` | Trigger pulse generation |
|  | `q_run` | Run program for N shots |

*(Table 2 of the paper, §6.1.)*

All five are RoCC custom0 instructions. The encoding fits the standard RoCC R-type layout, with the same funct7/funct3/rs1/rs2/rd fields you know from any Rocket-attached accelerator:

![RoCC instruction layout, paper Fig. 4](figures/isa_instructions.svg)

The next cells open the real tutorial C sources behind these instructions, then walk the compiled objdump output to confirm the emitted custom0 words match the paper-visible ISA surface.
"""


MD_RTYPE_FIELDS = """
Below is the packed instruction for a single `q_set` call, broken out field by field from the raw 32-bit word. The opcode is `custom0` (`0b0001011`); funct7 and funct3 together identify the instruction class; `rs1` points at the host-memory source; `rs2` carries the QAddress (destination segment base) and transfer length as a packed 64-bit payload. The QAddress is in the *payload*, never in the architectural instruction fields. That is how one opcode `q_set` can target any segment (`.program`, `.regfile`, …) in the quantum controller cache.
"""


MD_TWO_DATAPATHS = """
## Two on-chip datapaths

The ISA is the programmer-facing surface. Underneath, the quantum controller exposes **two distinct host-facing datapaths** into the quantum controller cache (QCC), plus two internal paths the user never touches. The programmer does not pick the datapath. The hardware routes based on the instruction class.

![Unified memory hierarchy and four datapaths, paper Fig. 3](figures/memory_space.svg)

| # | Connection | Interface | Latency | Serves |
| --- | --- | --- | --- | --- |
| ① | Host core register ↔ public QCC | RoCC | **1 cycle**, 64-bit | `q_update` |
| ② | Host L2 ↔ public QCC | QCC cache interface (TileLink) | Multi-cycle, bulk | `q_set`, `q_acquire` |
| ③ | Host L2 ↔ private QCC (QSpace) | Same as ② | — | Controller-managed (SLT spill) |
| ④ | QCC `.pulse` → quantum chip | ADI (16b × 2 DAC × 2 GHz) | 8 GB/s per qubit | Pulse output |

*(§5.2 of the paper. ① ② are the two host-visible paths. ③ ④ are internal.)*

The key point: **both ① and ② are inside the chip.** Neither crosses a network, a USB link, or a process boundary. The 1–10 ms decoupled baseline in Table 1 collapses because there is no longer a link to be slow.

The next few cells look at the concrete trace evidence for each path: first a `q_update` firing on path ①, then a `q_set` firing on path ②.
"""


MD_PATH2_DETAIL = """
Path ② is the bulk L2 ↔ public QCC connection. It carries `q_set` (host memory into `.program` / `.regfile`) and `q_acquire` (`.measure` back into host memory). Behind the scenes, the controller interface splits requests across a TileLink bus, reorders out-of-order responses via the RBQ, and packs 32-bit lanes in the WBQ. From the host's point of view that complexity is invisible: one `q_set` instruction, one destination QAddress, one transfer length. In the trace we can see the individual TileLink GETs and cache commits, and we can count cycles.

The captured trace below comes from one `q_set` moving program words into `.program` and one `q_update` dropping a 64-bit parameter payload straight into `.regfile`.
"""


MD_END_TO_END = """
## End-to-end consequence

Now we put the two paths to work inside an actual VQE-style iteration loop. The pattern is simple: iteration 0 sets up the program (bulk, path ②); iterations 1..K only update the variational parameter (register, path ①). Nothing about the program structure changes across iterations, so recompilation is unnecessary and the whole iteration becomes a single-cycle parameter swap plus a `q_gen` / `q_run` / `q_acquire` triple.

For this short demo, the target parameter pair is \((\theta_0,\theta_1)=(38,55)\). The notebook reports `progress_to_target`: 0% at the initial parameter pair and 100% when the loop reaches that target. The point is not to reproduce a physical VQE energy; it is to make the feedback loop visible while keeping the ISA/data-path story concrete.

This is what the paper calls "dynamic incremental compilation" (§6.1). It is not an optimization added on top of the ISA. It is a direct consequence of having two separate datapaths and letting the ISA pick the one that matches the data shape.

The second half of Act 3 covers fine-grained synchronization (§6.3): because the quantum controller cache writes to host memory via TileLink PUTs post-hoc, the host can start post-processing measurements from shot *i* while the controller is still running shots *i+1*, *i+2*, …:

![FENCE vs fine-grained synchronization, paper Fig. 6](figures/timing.svg)
"""


MD_SCOPE_CAVEAT = """
A note on scope before we dive in:

- **What the capture shows:** per-iteration `progress_to_target`, byte counts classified by datapath ① vs ②, plus a visual swimlane showing when the controller is busy with `q_run` and when the host CPU is free.
- **What the capture does not show:** the full ASIC timing behavior under realistic FENCE contention, or the 441.5× / 14.9× speedup numbers from the paper. Those require the 64-qubit workload and the ASIC host model (paper §7). Here we are showing that the ISA *permits* overlap and incremental updates; the magnitude numbers live in the slides.
"""


MD_CONCLUSION = """
## What this notebook did and did not do

This notebook showed:

1. **Programming model**: a hybrid quantum-classical loop written as one C program using five ISA extensions (Act 1).
2. **Hardware fabric**: two on-chip datapaths (RoCC single-cycle register path, TileLink bulk L2↔QCC path) replacing the decoupled USB/Ethernet link (Act 2).
3. **Runtime consequence**: iterations 1..K use the single-cycle path for parameter-only updates, and the memory consistency protocol permits the host to interleave post-processing with quantum execution (Act 3).

This notebook did **not** reproduce:

- the 441.5× classical-processing or 14.9× end-to-end speedup numbers, which require the full 64-qubit VQE workload and the ASIC host model (paper §7);
- the SLT skip-lookup behavior (datapath ③, controller-internal);
- the pulse output to physical DACs (datapath ④, no real quantum chip in this simulator);
- the full instruction scheduler's batched transmission policy (paper §6.2).

For any of those, read paper §5–§7 directly. The corresponding figures are under `paper_list/ISCA2025_Qtenon/pic/experiment/`.
"""


# ----- code cell sources -----------------------------------------------------


CODE_CELL_1_SETUP = '''
%matplotlib inline

import logging
import os
import sys
from pathlib import Path


def _discover_repo_root(start: Path) -> Path:
    anchor = start.resolve()
    for candidate in (anchor, *anchor.parents):
        if (candidate / "hw").is_dir() and (candidate / "software").is_dir():
            return candidate
    raise FileNotFoundError("Could not locate the Qtenon `code/` repository root.")


_repo_root = _discover_repo_root(Path.cwd())
os.chdir(_repo_root)
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

logging.basicConfig(level=logging.WARN)

from tutorial.helpers.common import TutorialPaths
from tutorial.helpers.encode import (
    COMMAND_FUNCT7,
    ENCODING_SPECS,
    decode_instruction,
    identify_command,
    pack_command,
    pack_q_set,
)
from tutorial.helpers.notebook_support import (
    CaptureMissing,
    compile_elf,
    ensure_simulator,
    find_objdump_line,
    format_table,
    load_capture_static,
    parse_hybrid_output,
    run_local_sim,
    source_block,
)
from tutorial.helpers.trace import (
    classify_path,
    parse_trace_text,
    split_hybrid_iterations,
)

paths = TutorialPaths.discover(Path.cwd())
'''


CODE_CELL_3_PREPARE = '''
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PreparedRun:
    capture: object
    elf_path: Path
    simulator_path: Path
    run_dir: Path
    chipyard_root: Path
    config_name: str
    uses_baked_cache: bool


run_dir = paths.tutorial_dir / "runs" / "hybrid_loop"
cache_files = [
    run_dir / "hybrid_loop.elf",
    run_dir / "hybrid_loop.log",
    run_dir / "hybrid_loop.objdump.txt",
    run_dir / "hybrid_loop.trace.txt",
]
use_baked_cache = (
    os.environ.get("QTENON_IGNORE_BAKED_CACHE") != "1"
    and all(path.is_file() for path in cache_files)
)

if use_baked_cache:
    elf_path = run_dir / "hybrid_loop.elf"
    elf_bytes = elf_path.stat().st_size
    compile_wall = 0.0
    simulator_path = Path(os.environ.get("QTENON_SIMULATOR", "/usr/local/bin/qtenon-sim"))
    sim_wall = 0.0
    sim_status = "(baked cache; simulator build skipped)"
else:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    elf_result = compile_elf(
        paths.tests_dir / "hybrid_loop_demo.c",
        run_dir / "hybrid_loop.elf",
    )
    compile_wall = time.perf_counter() - t0
    elf_path = Path(elf_result.elf_path)
    elf_bytes = elf_path.stat().st_size

    # Dump the fresh objdump so runs/ is self-contained.
    objdump_target = run_dir / "hybrid_loop.objdump.txt"
    if hasattr(elf_result, "objdump_text") and elf_result.objdump_text is not None:
        objdump_target.write_text(elf_result.objdump_text, encoding="utf-8")

    t1 = time.perf_counter()
    simulator_path = ensure_simulator(paths.chipyard_root, paths.config_name)
    sim_wall = time.perf_counter() - t1
    sim_status = "(no-op: binary already built)"

capture = load_capture_static(paths.captures_dir, "hybrid_loop")

prepared = PreparedRun(
    capture=capture,
    elf_path=elf_path,
    simulator_path=simulator_path,
    run_dir=run_dir,
    chipyard_root=paths.chipyard_root,
    config_name=paths.config_name,
    uses_baked_cache=use_baked_cache,
)

capture_trace_bytes = len(capture.trace_text.encode("utf-8"))

if use_baked_cache:
    print(
        f"Using baked Qtenon run cache…      {compile_wall:4.1f} s  "
        f"→  {prepared.elf_path.relative_to(paths.repo_root)} ({elf_bytes} B)"
    )
else:
    print(
        f"Cross-compiling hybrid_loop_demo.c…  {compile_wall:4.1f} s  "
        f"→  {prepared.elf_path.relative_to(paths.repo_root)} ({elf_bytes} B)"
    )
print(
    f"Ensuring Verilator simulator…        {sim_wall:4.1f} s  {sim_status}"
)
print()
print(
    "Toolchain ready. Simulation evidence lands at §End-to-end consequence; "
    "middle sections read captures/hybrid_loop/."
)
print()
print(
    format_table(
        ["elf path", "simulator binary", "capture trace bytes"],
        [[
            str(prepared.elf_path.relative_to(paths.repo_root)),
            str(prepared.simulator_path),
            capture_trace_bytes,
        ]],
    )
)
'''


CODE_CELL_5_TABLE2 = '''
host_action = {
    "q_set":     "host memory → QCC (bulk)",
    "q_update":  "host register → QCC (scalar)",
    "q_run":     "run program for N shots",
    "q_gen":     "trigger pulse generation",
    "q_acquire": "QCC → host memory (bulk)",
}

rows = []
for name, spec in ENCODING_SPECS.items():
    rows.append([
        name,
        spec.funct7,
        f"{spec.funct3:03b}",
        f"x{spec.rd}",
        host_action[name],
    ])

print(
    "Paper Table 2, mapped to the COMMAND_FUNCT7 / ENCODING_SPECS dict "
    "the rest of the notebook uses:"
)
print()
print(
    format_table(
        ["command", "funct7", "funct3", "rd (conv.)", "host action"],
        rows,
    )
)
'''


CODE_CELL_7_PACK_DECODE = '''
import re

rs1, rs2 = 8, 14
word = pack_q_set(rs1=rs1, rs2=rs2)

print(
    f"q_set(x{rs1}, x{rs2}) packs to:  0x{word:08x}  (32-bit RISC-V R-type)"
)
print()

decoded = decode_instruction(word)

field_rows = [
    ["opcode", "[6:0]",   f"0b{decoded['opcode']:07b}", "RoCC custom0"],
    ["funct7", "[31:25]", str(decoded['funct7']),       "q_set class (COMMAND_FUNCT7)"],
    ["funct3", "[14:12]", f"0b{decoded['funct3']:03b}", "q_set class (ENCODING_SPECS)"],
    ["rs1",    "[19:15]", f"x{decoded['rs1']}",         "host memory source register"],
    ["rs2",    "[24:20]", f"x{decoded['rs2']}",         "packed (QAddress | length) payload"],
    ["rd",     "[11:7]",  f"x{decoded['rd']}",          "no host register write"],
]

print(
    format_table(
        ["field", "bits", "value", "meaning"],
        field_rows,
    )
)

assert identify_command(decoded) == "q_set"
print()
print("Round-trip: identify_command(decoded) == 'q_set' ✓")
print()

print("The same word is emitted by the q_set(rs1, rs2) macro in rocc.h:")
print()
macro_source = source_block(paths.tests_dir / "rocc.h", "#define q_set", "}")
print(macro_source)
print()

print(
    "The `.insn r` template encodes the same opcode (0x0b) / funct3 (0b011) "
    "/ funct7 (0)"
)
print(
    "/ rd (x0) fields the table above just decoded; `%0 %1` are gcc "
    "inline-asm"
)
print(
    "placeholders the compiler fills with real RISC-V registers at "
    "emit time."
)
print()

rocc_h = paths.tests_dir / "rocc.h"


def _extract_insn_template(block: str) -> str:
    for line in block.splitlines():
        m = re.search(r'\\.insn r[^"]*"([^"]+)"', line)
        if m:
            return f'".insn r {m.group(1)}"' if not m.group(1).startswith(".insn") else f'"{m.group(1)}"'
        m2 = re.search(r'"(\\.insn r [^"]+)"', line)
        if m2:
            return f'"{m2.group(1)}"'
    return block.strip().splitlines()[0].strip()


macro_rows = []
for cmd in ["q_set", "q_update", "q_run", "q_gen"]:
    block = source_block(rocc_h, f"#define {cmd}", "}")
    template_line = next(
        (line for line in block.splitlines() if ".insn r" in line),
        None,
    )
    if template_line is not None:
        m = re.search(r'"(\\.insn r [^"]+)"', template_line)
        template = f'"{m.group(1)}"' if m else template_line.strip()
    else:
        template = block.strip().splitlines()[0].strip()
    macro_rows.append([cmd, template])

macro_rows.append([
    "q_acquire",
    "ROCC_INSTRUCTION_DS(0, rd, rs1, 6)    (funct7=6, funct3=0b110, rd=x10)",
])

print(
    "All five macros share the same .insn r pattern (differing only in "
    "funct3 / funct7 / rd):"
)
print()
print(format_table(["command", "macro source"], macro_rows))
'''


CODE_CELL_8_QSET_ROUNDTRIP = '''
parsed = parse_trace_text(prepared.capture.trace_text)
first_set = next(e for e in parsed if e.command == "q_set")

rs1 = first_set.decoded["rs1"]
rs2 = first_set.decoded["rs2"]
pc = first_set.pc
word = first_set.instruction

objdump_hit = find_objdump_line(prepared.capture.objdump_text, pc, word)
repacked = pack_q_set(rs1=rs1, rs2=rs2)

assert word == repacked, (
    f"Python pack produced 0x{repacked:08x}; trace carries 0x{word:08x}"
)
assert int(objdump_hit.hex_word, 16) == word, (
    f"objdump hex ({objdump_hit.hex_word}) does not match trace word "
    f"(0x{word:08x})"
)

print("First q_set in the hybrid_loop trace (from captures/hybrid_loop/):")
print()
print(f"  hybrid_loop.trace.txt  (line {first_set.line_number}):")
print(
    f"    C0:  cycle {first_set.cycle}   "
    f"pc=0x{pc:016x}   inst=0x{word:08x}"
)
print()
print("  hybrid_loop.objdump.txt  (matching pc):")
print(f"    {objdump_hit.raw_line}")
print()
print(f"  reconstructed from pack_q_set(rs1={rs1}, rs2={rs2}):")
print(f"    0x{repacked:08x}")
print()
print("✓ trace = objdump = Python pack: same 32-bit custom0 word")
print(
    f"  (rs1=x{rs1}, rs2=x{rs2} are the real RISC-V registers the compiler "
    "allocated"
)
print(
    "   for %0, %1 in the rocc.h q_set macro at this pc. §End-to-end"
)
print(
    "   consequence will re-run the same simulation live and the same byte"
)
print("   will show up at the same pc.)")
'''


CODE_CELL_10_PATH_CONTRAST = '''
parsed = [
    entry
    for entry in parse_trace_text(prepared.capture.trace_text)
    if entry.command is not None
]
assert len(parsed) == 16, f"expected 16 custom0 retire events, got {len(parsed)}"

iters = split_hybrid_iterations(parsed)

first_set = next(e for e in parsed if e.command == "q_set")
first_update = next(e for e in parsed if e.command == "q_update")


def _successor_in_same_iter(entry):
    for group in iters:
        if entry in group:
            idx = group.index(entry)
            if idx + 1 < len(group):
                return group[idx + 1], group
            return None, group
    return None, None


def _iter_index(group):
    return iters.index(group)


set_next, set_group = _successor_in_same_iter(first_set)
update_next, update_group = _successor_in_same_iter(first_update)
assert set_next is not None and update_next is not None, (
    "Expected q_set/q_update to have an immediate successor in the same iteration"
)

gap_set = set_next.cycle - first_set.cycle
gap_update = update_next.cycle - first_update.cycle

rows = []
for entry, successor_gap, group in (
    (first_set, gap_set, set_group),
    (first_update, gap_update, update_group),
):
    label = classify_path(entry.command)
    assert label in {"①", "②"}, f"classify_path({entry.command}) -> {label}"
    rows.append([
        label,
        entry.command,
        f"iter {_iter_index(group)}",
        f"0x{entry.pc:016x}",
        f"0x{entry.instruction:08x}",
        entry.cycle,
        f"+{successor_gap}",
    ])

print(
    format_table(
        ["path", "command", "from", "pc", "word", "retire cyc", "Δ to next"],
        rows,
    )
)
print()
print(
    f"path ① q_update → next = {gap_update} cyc   "
    f"(pure RoCC register write)"
)
print(
    f"path ② q_set    → next = {gap_set} cyc   "
    f"(RoCC + TileLink burst handshake; full timeline at Cell [14])"
)
'''


CODE_CELL_14_LIVE_SIM = '''
import os
import shutil
import time
from dataclasses import dataclass
from types import SimpleNamespace


@dataclass
class LiveRun:
    trace_text: str
    log_text: str
    objdump_text: str
    run_dir: object


run_dir = prepared.run_dir
use_baked_cache = (
    getattr(prepared, "uses_baked_cache", False)
    and os.environ.get("QTENON_IGNORE_BAKED_CACHE") != "1"
)

t0 = time.perf_counter()
if use_baked_cache:
    trace_text = (run_dir / "hybrid_loop.trace.txt").read_text(encoding="utf-8")
    log_text = (run_dir / "hybrid_loop.log").read_text(encoding="utf-8")
    objdump_path = run_dir / "hybrid_loop.objdump.txt"
    if not objdump_path.exists():
        shutil.copyfile(
            prepared.capture.objdump_path,
            objdump_path,
        )
    objdump_text = objdump_path.read_text(encoding="utf-8")
    parsed_for_counts = [
        entry
        for entry in parse_trace_text(trace_text)
        if entry.command is not None
    ]
    cycle_count = 0
    for entry in reversed(parsed_for_counts):
        if entry.cycle is not None:
            cycle_count = entry.cycle
            break
    result = SimpleNamespace(
        cycle_count=cycle_count,
        custom0_count=len(parsed_for_counts),
        iteration_count=4,
    )
else:
    result = run_local_sim(
        prepared.simulator_path,
        prepared.elf_path,
        run_dir,
        chipyard_root=prepared.chipyard_root,
        config_name=prepared.config_name,
    )
    trace_text = (run_dir / "hybrid_loop.trace.txt").read_text(encoding="utf-8")
    log_text = (run_dir / "hybrid_loop.log").read_text(encoding="utf-8")
    objdump_path = run_dir / "hybrid_loop.objdump.txt"
    if not objdump_path.exists():
        shutil.copyfile(
            prepared.capture.objdump_path,
            objdump_path,
        )
    objdump_text = objdump_path.read_text(encoding="utf-8")
wall = time.perf_counter() - t0


run = LiveRun(
    trace_text=trace_text,
    log_text=log_text,
    objdump_text=objdump_text,
    run_dir=run_dir,
)
cycles = getattr(result, "cycle_count", None)
custom0 = getattr(result, "custom0_count", None)
iters_n = getattr(result, "iteration_count", 4)
run_label = "Using baked simulation cache" if use_baked_cache else "Running simulation"
print(
    f"{run_label}…  {wall:4.1f} s  "
    f"({cycles} cycles, {custom0} custom0 insts, {iters_n} iterations)"
)

print()
print("UART output (read from hybrid_loop.log):")
for line in run.log_text.splitlines():
    stripped = line.rstrip()
    if not stripped:
        continue
    if stripped.startswith("iter,") or (
        "," in stripped and stripped.split(",", 1)[0].isdigit()
    ):
        print(f"  {stripped}")
print()

parsed = [
    entry
    for entry in parse_trace_text(run.trace_text)
    if entry.command is not None
]
assert len(parsed) == 16, f"expected 16 custom0 retires, got {len(parsed)}"
iters = split_hybrid_iterations(parsed)
assert len(iters) == 4, f"expected 4 iterations, got {len(iters)}"

rows = []
for iter_index, group in enumerate(iters):
    prev = None
    for entry in group:
        label = classify_path(entry.command)
        if prev is None:
            gap_str = "—"
        else:
            gap_str = f"+{entry.cycle - prev.cycle}"
        rows.append([
            iter_index,
            label,
            entry.command,
            f"0x{entry.pc:016x}",
            f"0x{entry.instruction:08x}",
            entry.cycle,
            gap_str,
        ])
        prev = entry

print(
    format_table(
        ["iter", "path", "command", "pc", "word", "retire cyc", "Δ prev cyc"],
        rows,
    )
)

import statistics


def _same_iter_successor_gaps(command):
    gaps = []
    for group in iters:
        for idx, entry in enumerate(group):
            if entry.command == command and idx + 1 < len(group):
                gaps.append(group[idx + 1].cycle - entry.cycle)
    return gaps


update_gaps = _same_iter_successor_gaps("q_update")
set_gaps = _same_iter_successor_gaps("q_set")
assert update_gaps, "expected at least one q_update → next gap"
assert set_gaps, "expected at least one q_set → next gap"

m_update = int(statistics.median(update_gaps))
n_set = set_gaps[0]

print()
print(
    f"q_update → next (iter 1..3, median) = {m_update} cyc   "
    f"(path ①; includes fetch bubble)"
)
print(
    f"q_set    → next (iter 0)            = {n_set} cyc   "
    f"(path ②; includes fetch bubble + TileLink handshake)"
)
print(
    f"Δ = {n_set - m_update} cyc reflects path ②'s TileLink handshake; "
    "numbers are retire-to-retire"
)
print(
    "gaps, not absolute transfer latency (see paper §5.2 for ASIC-scale "
    "numbers)."
)
'''


CODE_CELL_15_PROGRESS_PLOT = '''
import matplotlib.pyplot as plt

iters_data = parse_hybrid_output(run.log_text)
assert len(iters_data) == 4, f"expected 4 iteration rows, got {len(iters_data)}"

TARGET_THETA0 = 38
TARGET_THETA1 = 55


def distance_to_target(row):
    return (row.theta0_idx - TARGET_THETA0) ** 2 + (row.theta1_idx - TARGET_THETA1) ** 2


initial_distance = distance_to_target(iters_data[0])
assert initial_distance > 0, "initial parameters already match the target"

xs = [r.iteration for r in iters_data]
progress_percent = [
    100.0 * (1.0 - distance_to_target(r) / initial_distance)
    for r in iters_data
]

fig, ax = plt.subplots(figsize=(5.5, 3.0))
ax.plot(xs, progress_percent, marker="o", linewidth=1.5)
for r, y in zip(iters_data, progress_percent):
    ax.annotate(
        f"sb={r.sample_bits}",
        xy=(r.iteration, y),
        xytext=(0, 8),
        textcoords="offset points",
        ha="center",
        fontsize=8,
    )

ax.set_xlabel("iteration")
ax.set_ylabel("progress_to_target (%)")
ax.set_xticks(xs)
ax.set_ylim(-5, 105)
ax.grid(True, alpha=0.3)
ax.set_title("Progress toward target θ=(38,55)")
plt.tight_layout()
plt.show()

table_rows = [
    [
        r.iteration,
        r.theta0_idx,
        r.theta1_idx,
        r.sample_bits,
        f"{progress:.1f}%",
    ]
    for r, progress in zip(iters_data, progress_percent)
]

print(
    format_table(
        ["iter", "θ₀", "θ₁", "sample_bits", "progress_to_target"],
        table_rows,
    )
)
'''


CODE_CELL_16_COMPARISON = '''
iters_data = parse_hybrid_output(run.log_text)
assert len(iters_data) == 4, f"expected 4 iteration rows, got {len(iters_data)}"

# from software/tests/hybrid_loop_demo.c
SETUP_WORDS   = 128   # BULK_SETUP_WORDS  — length_words fed to pack_qaddress
UPDATE_BYTES  = 8     # one uint64_t dropped via q_update (path ①)
ACQUIRE_BYTES = 8     # one uint64_t pulled back via q_acquire (path ②)
SETUP_BYTES   = SETUP_WORDS * 2  # `short` elements in setup_words[]

rows = []
for r in iters_data:
    if r.iteration == 0:
        sequence = "q_set + q_gen + q_run + q_acquire"
        bytes_ii = SETUP_BYTES + ACQUIRE_BYTES
        bytes_i = 0
    else:
        sequence = "q_update + q_gen + q_run + q_acquire"
        bytes_ii = ACQUIRE_BYTES
        bytes_i = UPDATE_BYTES
    rows.append([
        r.iteration,
        sequence,
        bytes_ii,
        bytes_i,
        "no",
    ])

print(
    format_table(
        [
            "iter",
            "sequence",
            "bytes ②",
            "bytes ①",
            "recompile",
        ],
        rows,
    )
)
print()
print(
    f"iter 0   path ② bytes = {SETUP_BYTES + ACQUIRE_BYTES} B   "
    f"(one-time setup: {SETUP_BYTES} B program + {ACQUIRE_BYTES} B acquire)"
)
print(
    f"iter 1..3 path ① bytes = {UPDATE_BYTES} B each  "
    f"(incremental update) + {ACQUIRE_BYTES} B path ② acquire"
)
print(
    "Once the program is in QCC, every subsequent iteration is an 8-byte "
    "register write."
)
print(
    "No recompile, no bulk DMA. That is the end-to-end consequence of"
)
print(
    "splitting host↔QCC traffic into two paths behind one ISA."
)
'''


# ----- cell list -------------------------------------------------------------


def build_notebook() -> dict[str, object]:
    cells: list[dict[str, object]] = [
        # Cell [0] md — Why Qtenon exists
        markdown_cell(MD_WHY_QTENON, cell_id="94ae6f36"),
        # Cell [1] code — environment setup (silent)
        code_cell(CODE_CELL_1_SETUP, cell_id="c1-env-setup"),
        # Cell [2] md — Setup (v3 rewrite + heading rename)
        markdown_cell(MD_SETUP_V3, cell_id="72c805ae"),
        # Cell [3] code — compile ELF + ensure_simulator (no run)
        code_cell(CODE_CELL_3_PREPARE, cell_id="c3-prepare-run"),
        # Cell [4] md — Programming model (heading rename, body frozen)
        markdown_cell(MD_PROGRAMMING_MODEL, cell_id="2f5c528a"),
        # Cell [5] code — paper Table 2 from ENCODING_SPECS
        code_cell(CODE_CELL_5_TABLE2, cell_id="c5-table2"),
        # Cell [6] md — R-type field breakdown (frozen)
        markdown_cell(MD_RTYPE_FIELDS, cell_id="5ce74eb3"),
        # Cell [7] code — pack_q_set field decode + rocc.h macro + 5-row table
        code_cell(CODE_CELL_7_PACK_DECODE, cell_id="c7-pack-decode"),
        # Cell [8] code — first q_set round-trip from prepared.capture
        code_cell(CODE_CELL_8_QSET_ROUNDTRIP, cell_id="c8-qset-roundtrip"),
        # Cell [9] md — Two on-chip datapaths (heading rename, body frozen)
        markdown_cell(MD_TWO_DATAPATHS, cell_id="bee9b09e"),
        # Cell [10] code — small-sample path ①/② contrast
        code_cell(CODE_CELL_10_PATH_CONTRAST, cell_id="c10-path-contrast"),
        # Cell [11] md — Path ② detail (frozen)
        markdown_cell(MD_PATH2_DETAIL, cell_id="19ae4f9c"),
        # Cell [12] md — End-to-end consequence (heading rename, body frozen)
        markdown_cell(MD_END_TO_END, cell_id="8eb5cd77"),
        # Cell [13] md — End-to-end scope caveat (frozen)
        markdown_cell(MD_SCOPE_CAVEAT, cell_id="ff39d455"),
        # Cell [14] code — end-to-end simulation evidence
        code_cell(CODE_CELL_14_LIVE_SIM, cell_id="c14-live-sim"),
        # Cell [15] code — per-iteration progress line plot
        code_cell(CODE_CELL_15_PROGRESS_PLOT, cell_id="c15-objective-plot"),
        # Cell [16] code — end-to-end comparison table
        code_cell(CODE_CELL_16_COMPARISON, cell_id="c16-comparison-table"),
        # Cell [17] md — What this notebook did and did not do (heading rename)
        markdown_cell(MD_CONCLUSION, cell_id="6e241095"),
    ]

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Qtenon",
                "language": "python",
                "name": "qtenon",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    output_path = Path(__file__).with_name("qtenon_tutorial.ipynb")
    notebook = build_notebook()
    output_path.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
