#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOPIC_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${TOPIC_ROOT}/.." && pwd)"
IMAGE_TAG="${JANUS4_DOCKER_TAG:-janusq/janus4:isca2026}"
PLATFORM_FLAG="${JANUS4_DOCKER_PLATFORM:-linux/amd64}"
NOTEBOOK="tutorial/3_1_artery_feedback_tutorial.ipynb"

cd "${REPO_ROOT}"

docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" .

docker run --rm --platform "${PLATFORM_FLAG}" -i "${IMAGE_TAG}" /opt/artery-venv/bin/python - <<'PY'
import numpy
import scipy
import sklearn
import matplotlib

print("ARTERY imports passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/3-artery "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
  --to notebook \
  --execute "${NOTEBOOK}" \
  --ExecutePreprocessor.kernel_name=artery \
  --ExecutePreprocessor.timeout=600 \
  --output /tmp/artery-smoke.ipynb
