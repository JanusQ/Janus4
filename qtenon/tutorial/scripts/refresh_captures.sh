#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TUTORIAL_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd -- "${TUTORIAL_DIR}/.." && pwd)"
CAPTURE_ROOT="${TUTORIAL_DIR}/captures"
# Entire batch is staged here; nothing under ${CAPTURE_ROOT} is touched
# until the final atomic swap at the bottom of the script succeeds.
CAPTURE_STAGING="${TUTORIAL_DIR}/captures.tmp"

HOST="${QTENON_U200_HOST:-U200}"
REMOTE_ROOT="${QTENON_U200_CHIPYARD_ROOT:-~/firesim/target-design/chipyard}"
CONFIG_NAME="${QTENON_CONFIG_NAME:-QChipRocketConfig}"
VERILATOR_CMD="${QTENON_VERILATOR:-/home/taochenning/firesim/.conda-env/bin/verilator --main --timing --cc --exe}"
REBUILD_SIM="${QTENON_REBUILD_SIM:-1}"
SSH_OPTS=(
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=5
  -o BatchMode=yes
  -o ControlMaster=no
  -o ControlPath=none
)

remote_path() {
  local path="$1"
  if [[ "${path}" == "~/"* ]]; then
    printf '$HOME/%s' "${path#"~/"}"
  else
    printf '%q' "${path}"
  fi
}

run_remote() {
  local command="$1"
  ssh "${SSH_OPTS[@]}" "${HOST}" "bash -lc $(printf '%q' "${command}")"
}

copy_remote_file() {
  local remote_file="$1"
  local local_file="$2"
  mkdir -p "$(dirname "${local_file}")"
  rsync -av --quiet -e "ssh ${SSH_OPTS[*]}" "${HOST}:${remote_file}" "${local_file}"
}

filter_trace() {
  local raw_trace="$1"
  local filtered_trace="$2"
  PYTHONPATH="${REPO_ROOT}" python3 - "$raw_trace" "$filtered_trace" <<'PY'
from pathlib import Path
import sys

from tutorial.helpers.trace import filter_trace

raw_path = Path(sys.argv[1])
filtered_path = Path(sys.argv[2])
filtered_path.write_text(
    filter_trace(raw_path.read_text(encoding="utf-8")),
    encoding="utf-8",
)
PY
}

annotate_objdump() {
  local objdump_path="$1"
  PYTHONPATH="${REPO_ROOT}" python3 - "$objdump_path" <<'PY'
from pathlib import Path
import re
import sys

from tutorial.helpers.encode import decode_instruction, identify_command, CUSTOM0_OPCODE

path = Path(sys.argv[1])
lines = []
pattern = re.compile(r"^(\s*[0-9a-f]+:\s+)([0-9a-f]{8})(\s+)(.*)$")

for line in path.read_text(encoding="utf-8").splitlines():
    match = pattern.match(line)
    if match is None:
        lines.append(line)
        continue
    word = int(match.group(2), 16)
    if word & 0x7F != CUSTOM0_OPCODE:
        lines.append(line)
        continue
    command = identify_command(decode_instruction(word))
    if command is None:
        lines.append(line)
        continue
    lines.append(f"{line}    # {command}")

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

cpu_count() {
  if command -v getconf >/dev/null 2>&1; then
    getconf _NPROCESSORS_ONLN && return
  fi
  if command -v sysctl >/dev/null 2>&1; then
    sysctl -n hw.ncpu && return
  fi
  echo 4
}

# Whole-batch atomicity: any non-zero exit anywhere below tears down the
# staging directory so ${CAPTURE_ROOT} keeps its pre-refresh state intact.
# The swap at the bottom clears the trap itself once the move is done.
cleanup_staging() {
  if [[ -d "${CAPTURE_STAGING}" ]]; then
    echo "refresh_captures: aborting — cleaning ${CAPTURE_STAGING}" >&2
    rm -rf "${CAPTURE_STAGING}"
  fi
}
trap cleanup_staging EXIT INT TERM

readonly REMOTE_ROOT_CMD="$(remote_path "${REMOTE_ROOT}")"
readonly REMOTE_TESTS_DIR="${REMOTE_ROOT}/tests"
readonly REMOTE_SIM_DIR="${REMOTE_ROOT}/sims/verilator"
readonly REMOTE_OUTPUT_DIR="${REMOTE_SIM_DIR}/output/chipyard.harness.TestHarness.${CONFIG_NAME}"
readonly REMOTE_VERILATOR_ARG="$(printf '%q' "${VERILATOR_CMD}")"
readonly JOBS="${JOBS:-$(cpu_count)}"

mkdir -p "${CAPTURE_ROOT}"
rm -rf "${CAPTURE_STAGING}"
mkdir -p "${CAPTURE_STAGING}"
echo "refresh_captures: atomic swap mode — staging under ${CAPTURE_STAGING}" >&2

"${REPO_ROOT}/tools/sync_to_u200.sh" --host "${HOST}" --root "${REMOTE_ROOT}"

run_remote "cd ${REMOTE_ROOT_CMD}/tests && source ../tutorial_env.sh && make clean && make hybrid_loop_demo.riscv"

if [[ "${REBUILD_SIM}" != "0" ]]; then
  run_remote "cd ${REMOTE_ROOT_CMD}/sims/verilator && source ../../tutorial_env.sh && make -j${JOBS} CONFIG=${CONFIG_NAME} VERILATOR=${REMOTE_VERILATOR_ARG}"
fi

declare -a PROGRAM_SPECS=(
  "hybrid_loop_demo:hybrid_loop"
)

for spec in "${PROGRAM_SPECS[@]}"; do
  program="${spec%%:*}"
  capture_name="${spec##*:}"
  # Each capture is collected inside the single whole-batch staging dir
  # so a mid-batch failure leaves ${CAPTURE_ROOT} untouched.
  capture_stage_dir="${CAPTURE_STAGING}/${capture_name}"
  mkdir -p "${capture_stage_dir}"

  run_remote "cd ${REMOTE_ROOT_CMD}/sims/verilator && source ../../tutorial_env.sh && make run-binary CONFIG=${CONFIG_NAME} VERILATOR=${REMOTE_VERILATOR_ARG} BINARY=../../tests/${program}.riscv"
  run_remote "cd ${REMOTE_ROOT_CMD}/tests && source ../tutorial_env.sh && riscv64-unknown-elf-objdump -d ${program}.riscv" > "${capture_stage_dir}/${capture_name}.objdump.txt"
  annotate_objdump "${capture_stage_dir}/${capture_name}.objdump.txt"

  copy_remote_file "${REMOTE_TESTS_DIR}/${program}.riscv" "${capture_stage_dir}/${capture_name}.elf"
  copy_remote_file "${REMOTE_OUTPUT_DIR}/${program}.out" "${capture_stage_dir}/${capture_name}.trace.raw.txt"
  filter_trace "${capture_stage_dir}/${capture_name}.trace.raw.txt" "${capture_stage_dir}/${capture_name}.trace.txt"
  rm -f "${capture_stage_dir}/${capture_name}.trace.raw.txt"
  copy_remote_file "${REMOTE_OUTPUT_DIR}/${program}.log" "${capture_stage_dir}/${capture_name}.log"
done

CAPTURE_DATE_UTC="$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
PY
)"

VERILATOR_VERSION="$(run_remote "${VERILATOR_CMD} --version" | tail -n 1)"
# sha256 of the remote gcc binary so conda-env upgrades that swap the
# toolchain underneath us are visible in meta.json — just comparing
# verilator_version isn't enough because the RISC-V compiler can drift
# separately. Expectation: riscv64-unknown-elf-gcc on PATH under
# tutorial_env.sh; sha256sum on the binary (not the compile output).
TOOLCHAIN_SHA256="$(run_remote "source ${REMOTE_ROOT_CMD}/tutorial_env.sh >/dev/null 2>&1 && sha256sum \$(command -v riscv64-unknown-elf-gcc) | awk '{print \$1}'")"
GIT_HEAD="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
HW_TREE_HEAD="$(git -C "${REPO_ROOT}" rev-parse HEAD:hw 2>/dev/null || echo "${GIT_HEAD}")"
TUTORIAL_TREE_HEAD="$(git -C "${REPO_ROOT}" rev-parse HEAD:tutorial 2>/dev/null || echo "${GIT_HEAD}")"
GIT_DIRTY="false"
if [[ -n "$(git -C "${REPO_ROOT}" status --short)" ]]; then
  GIT_DIRTY="true"
fi

export CAPTURE_STAGING CAPTURE_DATE_UTC VERILATOR_VERSION TOOLCHAIN_SHA256 GIT_HEAD HW_TREE_HEAD TUTORIAL_TREE_HEAD GIT_DIRTY CONFIG_NAME
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

# meta.json is written inside the staging directory alongside the fresh
# per-capture subdirs. The final swap moves captures/ + meta.json
# together, so meta.json is never out-of-sync with the archive it
# describes.
capture_root = Path(os.environ["CAPTURE_STAGING"])
records = {}
for name in ("hybrid_loop",):
    elf_path = capture_root / name / f"{name}.elf"
    records[name] = {
        "elf_sha256": hashlib.sha256(elf_path.read_bytes()).hexdigest(),
        "elf_bytes": elf_path.stat().st_size,
        "trace_bytes": (capture_root / name / f"{name}.trace.txt").stat().st_size,
        "log_bytes": (capture_root / name / f"{name}.log").stat().st_size,
    }

config_path = (
    Path(os.environ["CAPTURE_STAGING"]).parents[1]
    / "hw" / "qc" / "src" / "main" / "scala" / "config" / "RoCCAcceleratorConfigs.scala"
)
meta = {
    "schema_version": 3,
    "captured_at_utc": os.environ["CAPTURE_DATE_UTC"],
    "git_head": os.environ["GIT_HEAD"],
    "git_dirty": os.environ["GIT_DIRTY"] == "true",
    "hw_tree_head": os.environ["HW_TREE_HEAD"],
    "tutorial_tree_head": os.environ["TUTORIAL_TREE_HEAD"],
    "config_name": os.environ["CONFIG_NAME"],
    "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    "verilator_version": os.environ["VERILATOR_VERSION"],
    "toolchain_sha256": os.environ["TOOLCHAIN_SHA256"],
    "artifacts": records,
}
meta_path = capture_root / "meta.json"
meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

# Carry checked-in static files (e.g. README.md) from the old captures/
# into the staging dir so the atomic swap below does not lose them. The
# refresh script only owns capture subdirs + meta.json; anything else is
# preserved as-is.
if [[ -d "${CAPTURE_ROOT}" ]]; then
  shopt -s nullglob dotglob
  for preserved in "${CAPTURE_ROOT}"/*; do
    name="$(basename "${preserved}")"
    case "${name}" in
      meta.json|meta.json.tmp|hybrid_loop)
        # Owned by this script — do not carry the stale copy forward.
        ;;
      *)
        if [[ ! -e "${CAPTURE_STAGING}/${name}" ]]; then
          cp -a "${preserved}" "${CAPTURE_STAGING}/${name}"
        fi
        ;;
    esac
  done
  shopt -u nullglob dotglob
fi

# Whole-batch atomic swap: one directory rename replaces the old
# captures/ with the freshly staged tree. captures.bak is only live for
# the window between the two renames; a crash between them leaves the
# .bak copy around for manual recovery and the staging cleanup trap a
# no-op (CAPTURE_STAGING no longer exists at that point).
CAPTURE_BACKUP="${TUTORIAL_DIR}/captures.bak"
rm -rf "${CAPTURE_BACKUP}"
if [[ -d "${CAPTURE_ROOT}" ]]; then
  mv "${CAPTURE_ROOT}" "${CAPTURE_BACKUP}"
fi
mv "${CAPTURE_STAGING}" "${CAPTURE_ROOT}"
rm -rf "${CAPTURE_BACKUP}"
trap - EXIT INT TERM

echo "Captured artifacts written to ${CAPTURE_ROOT}"
