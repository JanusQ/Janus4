#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOPIC_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${TOPIC_ROOT}/.." && pwd)"
IMAGE_TAG="${JANUS4_DOCKER_TAG:-janusq/janus4:isca2026}"
PLATFORM_FLAG="${JANUS4_DOCKER_PLATFORM:-linux/amd64}"
NOTEBOOK="tutorial/qram_tutorial.ipynb"
NOTEBOOK_TIMEOUT="${QRAM_NOTEBOOK_TIMEOUT:-600}"

cd "${REPO_ROOT}"

docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" .

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/6-EXP-QRAM -i "${IMAGE_TAG}" /opt/qram-venv/bin/python - <<'PY'
from qram.config import Config
from qram.qramtemplate.buckdatacell import Qram, cswap_depth, swap_depth

print("QRAM imports passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/6-EXP-QRAM "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
  --to notebook \
  --execute "${NOTEBOOK}" \
  --ExecutePreprocessor.kernel_name=qram \
  --ExecutePreprocessor.timeout="${NOTEBOOK_TIMEOUT}" \
  --output /tmp/qram-smoke.ipynb
