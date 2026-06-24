#!/usr/bin/env bash
set -euo pipefail

# Build-time Qtenon notebook cache.
#
# Docker runs this once while building the Janus4 image. Docker's layer cache
# then keeps the executed notebook evidence unless the Qtenon topic files
# change. The notebook default is replay-only, so live simulator run artifacts
# under tutorial/runs/ are recorded when present but are not required.

CACHE_DIR="${QTENON_SMOKE_CACHE_DIR:-/opt/qtenon-smoke-cache}"
TIMEOUT="${QTENON_NOTEBOOK_TIMEOUT:-1200}"
EXECUTED_NOTEBOOK="${CACHE_DIR}/qtenon_tutorial.executed.ipynb"

mkdir -p "${CACHE_DIR}"

python -m tutorial.validate_notebook \
  --timeout "${TIMEOUT}" \
  --output "${EXECUTED_NOTEBOOK}"

python - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

cache_dir = Path(os.environ.get("QTENON_SMOKE_CACHE_DIR", "/opt/qtenon-smoke-cache"))
executed_notebook = cache_dir / "qtenon_tutorial.executed.ipynb"
run_root = Path("tutorial/runs")
required = [executed_notebook]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit("Qtenon build cache is incomplete: " + ", ".join(missing))

optional_artifacts = []
if run_root.exists():
    optional_artifacts = sorted(path for path in run_root.rglob("*") if path.is_file())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe(path: Path) -> dict[str, object]:
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


metadata = {
    "schema_version": 2,
    "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "cache_contract": "executed_notebook_required_live_run_artifacts_optional",
    "executed_notebook": str(executed_notebook),
    "optional_run_root": str(run_root),
    "optional_run_artifact_count": len(optional_artifacts),
    "files": {
        str(path): describe(path)
        for path in [*required, *optional_artifacts]
    },
}
cache_dir.mkdir(parents=True, exist_ok=True)
cache_metadata = cache_dir / "metadata.json"
cache_metadata.write_text(
    json.dumps(metadata, indent=2, sort_keys=True),
    encoding="utf-8",
)
print(
    f"Qtenon build cache written to {cache_dir} "
    f"({len(optional_artifacts)} optional run artifacts)"
)
PY
