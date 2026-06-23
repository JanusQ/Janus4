#!/usr/bin/env bash
set -euo pipefail

# Build-time Qtenon notebook cache.
#
# Docker runs this once while building the Janus4 image. Docker's layer cache
# then keeps the expensive compiled ELF, simulator trace/log, and executed
# notebook unless the Qtenon topic files change.

CACHE_DIR="${QTENON_SMOKE_CACHE_DIR:-/opt/qtenon-smoke-cache}"
TIMEOUT="${QTENON_NOTEBOOK_TIMEOUT:-1200}"
EXECUTED_NOTEBOOK="${CACHE_DIR}/qtenon_tutorial.executed.ipynb"
RUN_DIR="tutorial/runs/hybrid_loop"

mkdir -p "${CACHE_DIR}"

QTENON_IGNORE_BAKED_CACHE=1 \
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
run_dir = Path("tutorial/runs/hybrid_loop")
required = [
    cache_dir / "qtenon_tutorial.executed.ipynb",
    run_dir / "hybrid_loop.elf",
    run_dir / "hybrid_loop.log",
    run_dir / "hybrid_loop.objdump.txt",
    run_dir / "hybrid_loop.trace.txt",
]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit("Qtenon build cache is incomplete: " + ", ".join(missing))

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

metadata = {
    "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "executed_notebook": str(required[0]),
    "run_dir": str(run_dir),
    "files": {
        str(path): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in required
    },
}
cache_dir.mkdir(parents=True, exist_ok=True)
(cache_dir / "metadata.json").write_text(
    json.dumps(metadata, indent=2, sort_keys=True),
    encoding="utf-8",
)
print(f"Qtenon build cache written to {cache_dir}")
PY
