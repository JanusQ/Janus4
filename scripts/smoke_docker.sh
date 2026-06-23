#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/qtenon_baked_cache.sh"

IMAGE_TAG="${JANUS4_DOCKER_TAG:-janusq/janus4:isca2026}"
PLATFORM_FLAG="${JANUS4_DOCKER_PLATFORM:-linux/amd64}"
CHOCOQ_NOTEBOOK="tutorial/6_1_constrained_binary_optimization.ipynb"
ADAPTDQC_NOTEBOOK="tutorial/adaptdqc_tutorial.ipynb"

cd "${REPO_ROOT}"

docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" .

qtenon_verify_baked_cache "${IMAGE_TAG}" "${PLATFORM_FLAG}"

docker run --rm --platform "${PLATFORM_FLAG}" -i "${IMAGE_TAG}" /opt/chocoq-venv/bin/python - <<'PY'
from chocoq.model import LinearConstrainedBinaryOptimization
from chocoq.solvers.optimizers import CobylaOptimizer
from chocoq.solvers.qiskit import AerProvider, ChocoSolver, DdsimProvider

print("Choco-Q imports passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/4-adaptDQC -i "${IMAGE_TAG}" /opt/adaptdqc-venv/bin/python - <<'PY'
from adaptivedqc.assessment import QPU
from adaptivedqc.assignQubit.compile import Partcompile
from adaptivedqc.hypridDQC.wireCut import CutWire

print("AdaptDQC imports passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/5-Choco-Q "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
    --to notebook \
    --execute "${CHOCOQ_NOTEBOOK}" \
    --ExecutePreprocessor.kernel_name=chocoq \
    --ExecutePreprocessor.timeout=600 \
    --output /tmp/chocoq-smoke.ipynb

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/4-adaptDQC "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
    --to notebook \
    --execute "${ADAPTDQC_NOTEBOOK}" \
    --ExecutePreprocessor.kernel_name=adaptiveqc \
    --ExecutePreprocessor.timeout=600 \
    --output /tmp/adaptdqc-smoke.ipynb
