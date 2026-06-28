#!/usr/bin/env bash
set -euo pipefail

# Smoke test for the Qtenon ISCA 2026 tutorial Docker image.
# Builds janusq/qtenon:isca2026 from the parent repo root (where the
# Dockerfile lives, alongside this code/ subrepo), then runs
# `python -m tutorial.validate_notebook` inside a fresh container.
# Exits non-zero on any cell failure or non-zero validate_notebook exit.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TUTORIAL_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
CODE_ROOT="$(cd -- "${TUTORIAL_DIR}/.." && pwd)"
REPO_ROOT="$(cd -- "${CODE_ROOT}/.." && pwd)"

IMAGE_TAG="${QTENON_DOCKER_TAG:-janusq/qtenon:isca2026}"
PLATFORM_FLAG="${QTENON_DOCKER_PLATFORM:-linux/amd64}"

if [[ ! -f "${REPO_ROOT}/Dockerfile" ]]; then
  echo "[smoke] ERROR: Dockerfile not found at ${REPO_ROOT}/Dockerfile" >&2
  exit 2
fi

if [[ ! -f "${REPO_ROOT}/build/qtenon-toolchain-amd64.tar.gz" ]] \
   || [[ ! -f "${REPO_ROOT}/build/qtenon-sim-libs-amd64.tar.gz" ]] \
   || [[ ! -f "${REPO_ROOT}/build/simulator-chipyard.harness-QChipRocketConfig" ]]; then
  echo "[smoke] ERROR: build/ artefacts missing — see code/docs/DOCKER.md image rebuild flow" >&2
  exit 2
fi

echo "[smoke] building ${IMAGE_TAG} from ${REPO_ROOT}"
docker build --platform "${PLATFORM_FLAG}" -t "${IMAGE_TAG}" "${REPO_ROOT}"

echo "[smoke] running validate_notebook inside ${IMAGE_TAG}"
docker run --rm --platform "${PLATFORM_FLAG}" "${IMAGE_TAG}" \
  python -m tutorial.validate_notebook

echo "[smoke] OK"
