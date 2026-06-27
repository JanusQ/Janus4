#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOPIC_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${TOPIC_ROOT}/.." && pwd)"
IMAGE_TAG="${JANUS4_DOCKER_TAG:-janusq/janus4:isca2026}"
PLATFORM_FLAG="${JANUS4_DOCKER_PLATFORM:-linux/amd64}"
NOTEBOOK="tutorial/adaptdqc_tutorial.ipynb"

cd "${REPO_ROOT}"

docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" .

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/3-adaptDQC -i "${IMAGE_TAG}" /opt/adaptdqc-venv/bin/python - <<'PY'
from adaptivedqc.assessment import QPU
from adaptivedqc.assignQubit.compile import Partcompile
from adaptivedqc.hypridDQC.wireCut import CutWire

print("AdaptDQC imports passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/3-adaptDQC "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
  --to notebook \
  --execute "${NOTEBOOK}" \
  --ExecutePreprocessor.kernel_name=adaptiveqc \
  --ExecutePreprocessor.timeout=600 \
  --output /tmp/adaptdqc-smoke.ipynb
