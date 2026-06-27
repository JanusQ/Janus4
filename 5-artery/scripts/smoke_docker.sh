#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOPIC_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${TOPIC_ROOT}/.." && pwd)"
IMAGE_TAG="${JANUS4_DOCKER_TAG:-janusq/janus4:isca2026}"
PLATFORM_FLAG="${JANUS4_DOCKER_PLATFORM:-linux/amd64}"
NOTEBOOK="5_1_artery_feedback_tutorial.ipynb"
NOTEBOOK_TIMEOUT="${ARTERY_NOTEBOOK_TIMEOUT:-600}"

cd "${REPO_ROOT}"

docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" .

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/5-artery/software -i "${IMAGE_TAG}" /opt/artery-venv/bin/python - <<'PY'
from pathlib import Path
import gzip

from quantum_feedback import QuantumFeedbackAnalyzer

data_path = Path("/workspace/5-artery/tutorial/s21_data.mat.gz")
if not data_path.is_file():
    raise SystemExit(f"Missing Artery S21 dataset: {data_path}")

with gzip.open(data_path, "rb") as source:
    header = source.read(128)
if not header.startswith(b"MATLAB"):
    raise SystemExit("Artery S21 dataset does not look like a MAT file")

print("Artery imports and S21 dataset passed")
PY

docker run --rm --platform "${PLATFORM_FLAG}" --workdir /workspace/5-artery/tutorial "${IMAGE_TAG}" \
  python -m jupyter nbconvert \
  --to notebook \
  --execute "${NOTEBOOK}" \
  --ExecutePreprocessor.kernel_name=artery \
  --ExecutePreprocessor.timeout="${NOTEBOOK_TIMEOUT}" \
  --output /tmp/artery-smoke.ipynb
