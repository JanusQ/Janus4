"""Generate the Qtenon tutorial notebook from v4 layout.

Cell list follows `.trellis/tasks/04-21-qtenon-demo-rewrite/cell_specs.md`
for the mechanism walkthrough, then appends a paper-figure reproduction
section for the VQE/SPSA time breakdown.
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

The paper claim we are servicing: end-to-end hybrid workloads run up to 14.9× faster than state-of-the-art decoupled architectures (Qtenon, ISCA 2025). This notebook does not reproduce the full speedup sweep. It first reproduces the mechanisms that produce it, then reruns one paper benchmark and redraws one paper experiment figure from the benchmark metrics plus the paper's evaluation assumptions.

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

The rest of this notebook turns the programming-model and data-movement parts of that table into code you can read and trace events you can check. The final paper-figure section uses the VQE/SPSA benchmark metrics and the paper Section 7 timing assumptions to regenerate the `time_breakdown` plot data.

![Qtenon system overview, paper Fig. 2](figures/qtenon_overview.svg)
"""


MD_SETUP_V3 = """
## Setup: replay captures by default

The notebook has two executable lanes:

| Lane | Source program | Default artifact | Purpose |
| --- | --- | --- | --- |
| Mechanism walkthrough | `software/tests/hybrid_loop_demo.c` | `tutorial/captures/hybrid_loop/` | show the ISA, datapaths, and `q_acquire` completion boundary on a small four-iteration loop |
| Paper figure reproduction | `software/tests/paper_vqe_spsa.c` | `tutorial/captures/paper_vqe_spsa/` | rerun/replay the 64-qubit VQE/SPSA benchmark and reconstruct `time_breakdown` |

The default tutorial path is replay-only. The next cell loads the
`hybrid_loop` capture for the mechanism sections; the later paper section
loads the separate `paper_vqe_spsa` capture. This keeps the notebook runnable
from the checked-in artifacts alone; the replay path does not require a local
RISC-V toolchain, Chipyard checkout, or Verilator build.

Contributors can opt into live simulation:

| Environment flag | What reruns |
| --- | --- |
| `QTENON_RUN_LIVE_SIM=1` | `hybrid_loop_demo.c` in Cell [14] |
| `QTENON_RUN_PAPER_EXPERIMENT=1` | `paper_vqe_spsa.c` in the paper-figure section |

Both live paths use `QChipRocketConfig` and are intentionally opt-in because a
full simulator build or run is machine-dependent and can take minutes.
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

Now we put the two paths to work inside an actual VQE-style iteration loop. The pattern is simple: iteration 0 sets up the program (bulk, path ②); iterations 1..K only update the variational parameter (register, path ①). Nothing about the program structure changes across iterations, so recompilation is unnecessary and the live trace should be read as a sequence/data-movement check: `q_set` appears once for setup, later iterations use `q_update`, and the same `q_gen` / `q_run` / `q_acquire` sequence consumes the prepared state.

This is what the paper calls "dynamic incremental compilation" (§6.1). It is not an optimization added on top of the ISA. It is a direct consequence of having two separate datapaths and letting the ISA pick the one that matches the data shape.

Important timing boundary: this tutorial backend now models `q_gen` as a 1000-cycle PGU countdown and `q_run` as shot-counted work, but those commands issue asynchronously from the host. The completion is therefore visible at the `q_acquire` → host-resume boundary, not in the retire gap from `q_gen` to `q_run`.

The second half of Act 3 covers fine-grained synchronization (§6.3): because the quantum controller cache writes to host memory via TileLink PUTs post-hoc, the host can start post-processing measurements from shot *i* while the controller is still running shots *i+1*, *i+2*, …:

![FENCE vs fine-grained synchronization, paper Fig. 6](figures/timing.svg)
"""


MD_SCOPE_CAVEAT = """
A note on scope before we dive in:

- **What the capture shows:** instruction issue order, per-iteration byte counts classified by datapath ① vs ②, and the `q_acquire` → host-resume waits where queued `q_gen`/`q_run` completion becomes visible.
- **What the Docker tutorial backend models:** `q_gen` snapshots the current tutorial parameters after a 1000-cycle PGU countdown; `q_run` computes a deterministic measurement word after shot-counted work. This makes the end-to-end loop visible and repeatable in a small simulator.
- **What the paper timing model adds:** full 64-qubit physical timing, ASIC host contention, and speedup modeling. The miniature backend only anchors the key latency dependency; it is not the paper's complete §7 performance model.
- **What the capture does not show:** full ASIC timing under realistic FENCE contention, or the 441.5× / 14.9× speedup numbers from the paper. Those require the 64-qubit workload and the ASIC host model (paper §7). Here we are showing that the ISA *permits* overlap and incremental updates; the magnitude numbers live in the slides/paper.
"""


MD_CONCLUSION = """
## What this notebook did and did not do

This notebook showed:

1. **Programming model**: a hybrid quantum-classical loop written as one C program using five ISA extensions (Act 1).
2. **Hardware fabric**: two on-chip datapaths (RoCC register path, TileLink bulk L2↔QCC path) replacing the decoupled USB/Ethernet link (Act 2).
3. **Runtime consequence**: iterations 1..K use the register path for parameter-only updates, and the memory consistency protocol permits the host to interleave post-processing with quantum execution (Act 3).
4. **Paper-figure reproduction path**: `paper_vqe_spsa.c` emits raw benchmark metrics, and the notebook applies the paper's Section 7 timing assumptions to redraw the 64-qubit VQE/SPSA `time_breakdown` figure.

This notebook did **not** reproduce:

- the 441.5× classical-processing or 14.9× end-to-end speedup numbers, which require the full 64-qubit VQE workload and the ASIC host model (paper §7);
- the full physical `q_run` quantum-execution timing and end-to-end speedup model from paper §7;
- the SLT skip-lookup behavior (datapath ③, controller-internal);
- the pulse output to physical DACs (datapath ④, no real quantum chip in this simulator);
- the full instruction scheduler's batched transmission policy (paper §6.2).

For any of those, read paper §5–§7 directly. The corresponding figures are under `paper_list/ISCA2025_Qtenon/pic/experiment/`.
"""


MD_PAPER_TIME_BREAKDOWN = """
## Paper figure reproduction: 64-qubit VQE/SPSA time breakdown

The target paper figure is `pic/experiment/time_breakdown.pdf`. Its caption is the end-to-end breakdown of **64-qubit VQE optimized by SPSA**, so this section uses `software/tests/paper_vqe_spsa.c`, not QAOA.

The figure has three panels:

| Panel | Meaning |
| --- | --- |
| (a) Baseline | Decoupled host + FPGA controller |
| (b) Qtenon w/o software | Qtenon hardware without the software optimizations |
| (c) Qtenon | Qtenon with the fine-grained synchronization / scheduling path |

This is still an evaluation-model figure. The benchmark run provides raw `rdcycle` / instruction-count metrics; the notebook then uses the benchmark's own `rdcycle` replay windows for the paper host-computation terms and applies the paper's evaluation assumptions for quantum execution, communication, and pulse generation. The `source` column below marks that boundary.
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
    COMPONENT_LABELS,
    DEFAULT_TIMING_ASSUMPTIONS,
    PAPER_VQE_CAPTURE,
    SCENARIO_LABELS,
    SCENARIO_ORDER,
    compile_elf,
    ensure_simulator,
    find_objdump_line,
    format_table,
    load_capture_static,
    paper_breakdown_plot_rows,
    paper_breakdown_table_rows,
    parse_hybrid_output,
    run_local_sim,
    run_paper_vqe_spsa,
    source_block,
)
from tutorial.helpers.trace import (
    classify_path,
    last_trace_cycle,
    parse_acquire_completion_waits,
    parse_trace_text,
    split_hybrid_iterations,
)

paths = TutorialPaths.discover(Path.cwd())
'''


CODE_CELL_3_PREPARE = '''
import shutil
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PreparedRun:
    capture: object
    run_dir: Path
    chipyard_root: Path
    config_name: str
    elf_path: Path | None = None
    simulator_path: Path | None = None


run_dir = paths.tutorial_dir / "runs" / "hybrid_loop"
if run_dir.exists():
    shutil.rmtree(run_dir)
run_dir.mkdir(parents=True, exist_ok=True)

capture = load_capture_static(paths.captures_dir, "hybrid_loop")

prepared = PreparedRun(
    capture=capture,
    run_dir=run_dir,
    chipyard_root=paths.chipyard_root,
    config_name=paths.config_name,
)

capture_trace_bytes = len(capture.trace_text.encode("utf-8"))
capture_cycles = last_trace_cycle(capture.trace_text) or 0
capture_custom0 = len(parse_trace_text(capture.trace_text))

print("Loaded checked-in hybrid_loop capture; no simulator run in setup.")
print()
print(
    "Set QTENON_RUN_LIVE_SIM=1 before executing the notebook to rebuild/run "
    "the local simulator at Cell [14]."
)
print("The paper_vqe_spsa capture is loaded later by the paper-figure section.")
print()
print(
    format_table(
        ["capture trace", "log", "custom0 insts", "last trace cyc", "trace bytes"],
        [[
            str(capture.trace_path.relative_to(paths.repo_root)),
            str(capture.log_path.relative_to(paths.repo_root)),
            capture_custom0,
            capture_cycles,
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

first_set = next(e for e in parsed if e.command == "q_set")
first_update = next(e for e in parsed if e.command == "q_update")

rows = []
for entry, role, payload_shape in (
    (
        first_set,
        "one-time setup",
        "program words via host memory + QAddress",
    ),
    (
        first_update,
        "per-iteration parameter update",
        "one 64-bit scalar carried in rs1",
    ),
):
    label = classify_path(entry.command)
    assert label in {"①", "②"}, f"classify_path({entry.command}) -> {label}"
    rows.append([
        label,
        entry.command,
        role,
        payload_shape,
        f"0x{entry.pc:016x}",
        f"0x{entry.instruction:08x}",
        entry.cycle,
    ])

print(
    format_table(
        ["path", "command", "role", "payload shape", "pc", "word", "retire cyc"],
        rows,
    )
)
print()
print(
    "Read this table as an ISA/datapath check, not as a latency measurement."
)
print(
    "The retire cycle identifies where the instruction appears in the trace; "
    "paper-level q_gen/q_run timing is not inferred from these gaps."
)
'''


CODE_CELL_14_LIVE_SIM = '''
import shutil
import time
from dataclasses import dataclass


@dataclass
class LiveRun:
    source: str
    trace_text: str
    log_text: str
    objdump_text: str
    run_dir: object


run_dir = prepared.run_dir
run_live = os.environ.get("QTENON_RUN_LIVE_SIM") == "1"

if run_live:
    t_compile = time.perf_counter()
    elf_result = compile_elf(
        paths.tests_dir / "hybrid_loop_demo.c",
        run_dir / "hybrid_loop.elf",
    )
    prepared.elf_path = Path(elf_result.elf_path)
    compile_wall = time.perf_counter() - t_compile

    t_sim_build = time.perf_counter()
    prepared.simulator_path = ensure_simulator(paths.chipyard_root, paths.config_name)
    sim_build_wall = time.perf_counter() - t_sim_build

    t0 = time.perf_counter()
    result = run_local_sim(
        prepared.simulator_path,
        prepared.elf_path,
        run_dir,
        chipyard_root=prepared.chipyard_root,
        config_name=prepared.config_name,
    )
    wall = time.perf_counter() - t0

    trace_text = (run_dir / "hybrid_loop.trace.txt").read_text(encoding="utf-8")
    log_text = (run_dir / "hybrid_loop.log").read_text(encoding="utf-8")
    objdump_path = run_dir / "hybrid_loop.objdump.txt"
    if not objdump_path.exists():
        shutil.copyfile(
            prepared.capture.objdump_path,
            objdump_path,
        )
    objdump_text = objdump_path.read_text(encoding="utf-8")
    source_label = "live simulator"
    cycles = getattr(result, "cycle_count", None)
    custom0 = getattr(result, "custom0_count", None)
    print(
        f"Running live simulation…  compile {compile_wall:4.1f} s, "
        f"ensure sim {sim_build_wall:4.1f} s, run {wall:4.1f} s  "
        f"({cycles} cycles, {custom0} custom0 insts)"
    )
else:
    trace_text = prepared.capture.trace_text
    log_text = prepared.capture.log_text
    objdump_text = prepared.capture.objdump_text
    source_label = "checked-in hybrid_loop capture replay"
    cycles = last_trace_cycle(trace_text)
    custom0 = len(parse_trace_text(trace_text))
    print(
        f"Replaying checked-in capture…  "
        f"({cycles} cycles, {custom0} custom0 insts)"
    )

run = LiveRun(
    source=source_label,
    trace_text=trace_text,
    log_text=log_text,
    objdump_text=objdump_text,
    run_dir=run_dir,
)

print()
print(f"Trace source: {run.source}")
print()
uart_iters = parse_hybrid_output(run.log_text)
assert len(uart_iters) == 4, f"expected 4 UART iteration rows, got {len(uart_iters)}"
print("UART iteration state (read from hybrid_loop.log):")
print(
    format_table(
        ["iter", "theta0_idx", "theta1_idx", "sample_bits", "acquire_word"],
        [
            [
                row.iteration,
                row.theta0_idx,
                row.theta1_idx,
                row.sample_bits,
                row.acquire_word_hex,
            ]
            for row in uart_iters
        ],
    )
)
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
    for entry in group:
        label = classify_path(entry.command)
        rows.append([
            iter_index,
            label,
            entry.command,
            f"0x{entry.pc:016x}",
            f"0x{entry.instruction:08x}",
            entry.cycle,
        ])

print(
    format_table(
        ["iter", "path", "command", "pc", "word", "retire cyc"],
        rows,
    )
)
print()

waits = parse_acquire_completion_waits(run.trace_text)
assert len(waits) == 4, f"expected 4 q_acquire completion waits, got {len(waits)}"
wait_rows = []
for wait in waits:
    wait_rows.append([
        wait.iteration,
        wait.q_gen_cycle,
        wait.q_run_cycle,
        wait.acquire_cycle,
        wait.resume_cycle,
        wait.acquire_to_resume_cycles,
        wait.gen_to_resume_cycles,
    ])

print(
    format_table(
        [
            "iter",
            "q_gen issue",
            "q_run issue",
            "q_acquire issue",
            "host resumes",
            "acquire→resume",
            "q_gen→resume",
        ],
        wait_rows,
    )
)
print()
print(
    "The first table is the custom0 issue trace. The second table is the "
    "completion-visible boundary: q_acquire issues, then the host does not "
    "retire another instruction until the queued PGU countdown plus shot-counted "
    "run has produced a measurement."
)
print()
print(
    "So q_run→q_acquire retire gaps are not q_run latency. The useful demo "
    "number is q_acquire→host-resume; q_gen→host-resume includes the 1000-cycle "
    "PGU anchor, the 128-shot run, and ordinary host/control overhead."
)
'''


CODE_CELL_PAPER_BREAKDOWN = '''
import math
import matplotlib.pyplot as plt

paper_run_dir = paths.tutorial_dir / "runs" / PAPER_VQE_CAPTURE
if paper_run_dir.exists():
    shutil.rmtree(paper_run_dir)
paper_run_dir.mkdir(parents=True, exist_ok=True)

paper_live = os.environ.get("QTENON_RUN_PAPER_EXPERIMENT") == "1"
paper_artifacts = run_paper_vqe_spsa(paths, paper_run_dir, live=paper_live)
paper_log = paper_artifacts.parsed
assert paper_log is not None

print(f"Paper experiment source: {paper_artifacts.source}")
print(
    "Set QTENON_RUN_PAPER_EXPERIMENT=1 before executing the notebook to "
    "re-run paper_vqe_spsa through Verilator."
)
print()
print("Step 1: raw simulator evidence")
print()
print(
    format_table(
        ["metric", "value"],
        [
            ["qubits", paper_log.metric("qubits")],
            ["shots", paper_log.metric("shots")],
            ["iterations", paper_log.metric("iterations")],
            ["parameters", paper_log.metric("parameters")],
            ["q_set_calls", paper_log.metric("q_set_calls")],
            ["q_update_calls", paper_log.metric("q_update_calls")],
            ["q_gen_calls", paper_log.metric("q_gen_calls")],
            ["q_run_calls", paper_log.metric("q_run_calls")],
            ["total_cycles", paper_log.metric("total_cycles")],
            ["qtenon_host_cycles_rdcycle", paper_log.metric("qtenon_host_cycles_rdcycle")],
            ["qtenon_without_software_host_cycles_rdcycle", paper_log.metric("qtenon_without_software_host_cycles_rdcycle")],
        ],
    )
)
print()
print("Step 2: paper timing model applied to that benchmark context")
print("Timing conversion: target core = 1 GHz, so 1 rdcycle tick = 1 ns.")
print()

assumptions = DEFAULT_TIMING_ASSUMPTIONS
raw_total_ms = paper_log.metric("total_cycles") * assumptions.target_cycle_ns / 1_000_000.0
wo_host_ms = paper_log.metric("qtenon_without_software_host_cycles_rdcycle") * assumptions.target_cycle_ns / 1_000_000.0
full_host_ms = paper_log.metric("qtenon_host_cycles_rdcycle") * assumptions.target_cycle_ns / 1_000_000.0
wo_comm_ms = assumptions.qtenon_without_software_comm_ns / 1_000_000.0
full_comm_ms = assumptions.qtenon_comm_ns / 1_000_000.0
pulse_ms = assumptions.qtenon_pulse_generation_ns / 1_000_000.0
quantum_ms = assumptions.quantum_execution_ns / 1_000_000.0
wo_total_ms = quantum_ms + wo_comm_ms + pulse_ms + wo_host_ms
full_total_ms = quantum_ms + full_comm_ms + pulse_ms + full_host_ms

print(
    format_table(
        ["item", "expression", "ms", "source"],
        [
            [
                "Verilator raw run",
                f"{paper_log.metric('total_cycles'):,} cycles @ 1 ns",
                f"{raw_total_ms:.6f}",
                "current simulator evidence, not the paper figure total",
            ],
            [
                "Qtenon w/o software host",
                f"{paper_log.metric('qtenon_without_software_host_cycles_rdcycle'):,} cycles @ 1 ns",
                f"{wo_host_ms:.6f}",
                "verilator rdcycle replay",
            ],
            [
                "Qtenon total host",
                f"{paper_log.metric('qtenon_host_cycles_rdcycle'):,} cycles @ 1 ns",
                f"{full_host_ms:.6f}",
                "verilator rdcycle replay",
            ],
            [
                "Qtenon w/o software total",
                (
                    f"{quantum_ms:.6f} + {wo_comm_ms:.6f} + "
                    f"{pulse_ms:.6f} + {wo_host_ms:.6f}"
                ),
                f"{wo_total_ms:.6f}",
                "paper model + verilator rdcycle",
            ],
            [
                "Qtenon total",
                (
                    f"{quantum_ms:.6f} + {full_comm_ms:.6f} + "
                    f"{pulse_ms:.6f} + {full_host_ms:.6f}"
                ),
                f"{full_total_ms:.6f}",
                "paper model + verilator rdcycle",
            ],
        ],
    )
)
print()

print("Step 3: rows used to redraw time_breakdown")
print()
table_rows = []
for scenario, component, total_ms, component_ms, percent, source in paper_breakdown_table_rows(paper_log):
    table_rows.append([
        scenario,
        component,
        f"{total_ms:.1f}",
        f"{component_ms:.4f}",
        f"{percent:g}%",
        source,
    ])

print(
    format_table(
        ["scenario", "component", "total ms", "component ms", "percent", "source"],
        table_rows,
    )
)

component_colors = {
    "quantum_execution": "#caa98f",
    "quantum_host_comm": "#af927a",
    "pulse_generation": "#f6d097",
    "host_computation": "#e7d2b6",
}

plot_rows = paper_breakdown_plot_rows(paper_log)
paper_component_order = [
    "quantum_execution",
    "pulse_generation",
    "host_computation",
    "quantum_host_comm",
]
panel_labels = {
    "baseline": "(a) Baseline",
    "qtenon_without_software": "(b) Qtenon w/o software",
    "qtenon": "(c) Qtenon",
}
panel_start_angles = {
    "baseline": 93,
    "qtenon_without_software": 347,
    "qtenon": 323,
}


def percent_label(percent):
    if percent < 0.1:
        return f"{percent:.2f}%"
    return f"{percent:.1f}".rstrip("0").rstrip(".") + "%"


def label_inside(scenario, component, percent):
    if component == "host_computation" and percent >= 7:
        return True
    if component == "quantum_host_comm" and scenario == "baseline":
        return True
    return percent >= 10


def label_radius(scenario, component, inside):
    if not inside:
        return 1.18
    if scenario == "qtenon" and component == "host_computation":
        return 0.72
    return 0.50


with plt.rc_context({
    "font.family": "serif",
    "font.size": 16,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
}):
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 5.7))
    fig.subplots_adjust(top=0.70, bottom=0.16, left=0.035, right=0.985, wspace=0.18)

    legend_order = ["quantum_execution", "quantum_host_comm", "pulse_generation", "host_computation"]
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=component_colors[key], edgecolor="black", linewidth=1.4)
        for key in legend_order
    ]
    legend_labels = [
        "Quantum execution",
        "Quantum-host comm.",
        "Pulse generation",
        "Host computation",
    ]
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.53, 0.99),
        columnspacing=1.8,
        handletextpad=0.55,
        fontsize=18,
    )

    for ax, scenario in zip(axes, SCENARIO_ORDER):
        rows_by_component = {row.component: row for row in plot_rows[scenario]}
        rows = [rows_by_component[key] for key in paper_component_order]
        sizes = [row.component_percent for row in rows]
        colors = [component_colors[row.component] for row in rows]
        explode = [0.055, 0.055, 0.055, 0.055]
        wedges, _ = ax.pie(
            sizes,
            colors=colors,
            explode=explode,
            startangle=panel_start_angles[scenario],
            counterclock=False,
            wedgeprops={"linewidth": 1.35, "edgecolor": "black"},
            radius=1.0,
        )

        for wedge, row in zip(wedges, rows):
            angle = (wedge.theta1 + wedge.theta2) / 2.0
            radians = angle * 3.141592653589793 / 180.0
            inside = label_inside(scenario, row.component, row.component_percent)
            radius = label_radius(scenario, row.component, inside)
            x = radius * math.cos(radians)
            y = radius * math.sin(radians)
            ha = "center" if inside else ("left" if x >= 0 else "right")
            color = "white" if row.component == "quantum_host_comm" and scenario == "baseline" else "black"
            ax.text(
                x,
                y,
                percent_label(row.component_percent),
                ha=ha,
                va="center",
                fontsize=18 if inside else 17,
                color=color,
            )

        total_ms = rows[0].total_ms
        ax.text(0, -1.33, f"{total_ms:.1f} ms", ha="center", va="center", fontsize=19, fontweight="bold")
        ax.text(0, -1.70, panel_labels[scenario], ha="center", va="center", fontsize=20)
        ax.set_xlim(-1.35, 1.35)
        ax.set_ylim(-1.85, 1.27)
        ax.axis("off")
        ax.set_aspect("equal")

    plt.show()
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
        # Cell [14] code — end-to-end live simulation climax
        code_cell(CODE_CELL_14_LIVE_SIM, cell_id="c14-live-sim"),
        # Cell [15] md — Paper figure reproduction scope
        markdown_cell(MD_PAPER_TIME_BREAKDOWN, cell_id="paper-breakdown-md"),
        # Cell [16] code — VQE/SPSA time_breakdown reproduction
        code_cell(CODE_CELL_PAPER_BREAKDOWN, cell_id="paper-breakdown-code"),
        # Cell [17] md — What this notebook did and did not do (heading rename)
        markdown_cell(MD_CONCLUSION, cell_id="6e241095"),
    ]

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
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
