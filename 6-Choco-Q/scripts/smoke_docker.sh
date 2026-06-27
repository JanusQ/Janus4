#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOPIC_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${TOPIC_ROOT}/.." && pwd)"
IMAGE_TAG="${JANUS4_DOCKER_TAG:-janusq/janus4:isca2026}"
PLATFORM_FLAG="${JANUS4_DOCKER_PLATFORM:-linux/amd64}"
NOTEBOOK="tutorial/6_1_constrained_binary_optimization.ipynb"

cd "${REPO_ROOT}"

docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" .

docker run --rm --platform "${PLATFORM_FLAG}" -i "${IMAGE_TAG}" /opt/chocoq-venv/bin/python - <<'PY'
from chocoq.model import LinearConstrainedBinaryOptimization
from chocoq.solvers.optimizers import CobylaOptimizer
from chocoq.solvers.qiskit import AerProvider, ChocoSolver, DdsimProvider

print("Choco-Q imports passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/6-Choco-Q "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
  --to notebook \
  --execute "${NOTEBOOK}" \
  --ExecutePreprocessor.kernel_name=chocoq \
  --ExecutePreprocessor.timeout=600 \
  --output /tmp/chocoq-smoke.ipynb
