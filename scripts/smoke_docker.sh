#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_TAG="${JANUS4_DOCKER_TAG:-janusq/janus4:isca2026}"
PLATFORM_FLAG="${JANUS4_DOCKER_PLATFORM:-linux/amd64}"
ARTERY_NOTEBOOK="tutorial/3_1_artery_feedback_tutorial.ipynb"
CHOCOQ_NOTEBOOK="tutorial/6_1_constrained_binary_optimization.ipynb"

cd "${REPO_ROOT}"

docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" .

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/2-qtenon "${IMAGE_TAG}" \
  python -m tutorial.validate_notebook

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/3-artery "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
    --to notebook \
    --execute "${ARTERY_NOTEBOOK}" \
    --ExecutePreprocessor.kernel_name=artery \
    --ExecutePreprocessor.timeout=600 \
    --output /tmp/artery-smoke.ipynb

docker run --rm --platform "${PLATFORM_FLAG}" -i "${IMAGE_TAG}" /opt/chocoq-venv/bin/python - <<'PY'
from chocoq.model import LinearConstrainedBinaryOptimization
from chocoq.solvers.optimizers import CobylaOptimizer
from chocoq.solvers.qiskit import AerProvider, ChocoSolver, DdsimProvider

print("Choco-Q imports passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/5-Choco-Q "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
    --to notebook \
    --execute "${CHOCOQ_NOTEBOOK}" \
    --ExecutePreprocessor.kernel_name=chocoq \
    --ExecutePreprocessor.timeout=600 \
    --output /tmp/chocoq-smoke.ipynb
