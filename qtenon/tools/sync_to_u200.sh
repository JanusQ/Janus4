#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./tools/sync_to_u200.sh [--dry-run] [--host U200] [--root ~/firesim/target-design/chipyard]
EOF
}

HOST="${QTENON_U200_HOST:-U200}"
REMOTE_ROOT="${QTENON_U200_CHIPYARD_ROOT:-~/firesim/target-design/chipyard}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --root)
      REMOTE_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RSYNC_ARGS=(-av)
SSH_ARGS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes -o ControlMaster=no -o ControlPath=none)
RSYNC_SSH="ssh ${SSH_ARGS[*]}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  RSYNC_ARGS+=(--dry-run)
fi

REMOTE_DIRS=(
  "${REMOTE_ROOT}/generators/qc/src/main/scala/qc"
  "${REMOTE_ROOT}/generators/chipyard/src/main/scala/config"
  "${REMOTE_ROOT}/tests"
)

ssh "${SSH_ARGS[@]}" "${HOST}" "mkdir -p ${REMOTE_DIRS[*]}"

rsync -e "${RSYNC_SSH}" "${RSYNC_ARGS[@]}" \
  "${REPO_ROOT}/hw/qc/src/main/scala/qc/" \
  "${HOST}:${REMOTE_ROOT}/generators/qc/src/main/scala/qc/"

rsync -e "${RSYNC_SSH}" "${RSYNC_ARGS[@]}" \
  "${REPO_ROOT}/hw/qc/src/main/scala/config/RoCCAcceleratorConfigs.scala" \
  "${HOST}:${REMOTE_ROOT}/generators/chipyard/src/main/scala/config/RoCCAcceleratorConfigs.scala"

rsync -e "${RSYNC_SSH}" "${RSYNC_ARGS[@]}" \
  --include='*.c' \
  --include='*.h' \
  --exclude='*' \
  "${REPO_ROOT}/software/tests/" \
  "${HOST}:${REMOTE_ROOT}/tests/"

rsync -e "${RSYNC_SSH}" "${RSYNC_ARGS[@]}" \
  "${REPO_ROOT}/tools/tutorial_env.sh" \
  "${HOST}:${REMOTE_ROOT}/tutorial_env.sh"
