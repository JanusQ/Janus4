#!/usr/bin/env bash

# Shared host-side verification for the Qtenon notebook cache baked into the
# Janus4 Docker image. Source this from scripts using `set -euo pipefail`.

qtenon_verify_baked_cache() {
  local image_tag="$1"
  local platform_flag="$2"

  docker run --rm --platform "${platform_flag}" --workdir /workspace/2-qtenon -i "${image_tag}" \
    python - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

cache_dir = Path("/opt/qtenon-smoke-cache")
executed_notebook = cache_dir / "qtenon_tutorial.executed.ipynb"
metadata_path = cache_dir / "metadata.json"
run_dir = Path("/workspace/2-qtenon/tutorial/runs/hybrid_loop")

required = [
    executed_notebook,
    metadata_path,
    run_dir / "hybrid_loop.elf",
    run_dir / "hybrid_loop.log",
    run_dir / "hybrid_loop.objdump.txt",
    run_dir / "hybrid_loop.trace.txt",
]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit("Qtenon baked notebook cache is missing: " + ", ".join(missing))

notebook = json.loads(executed_notebook.read_text(encoding="utf-8"))
errors: list[str] = []
code_cells = 0
for index, cell in enumerate(notebook.get("cells", [])):
    if cell.get("cell_type") != "code":
        continue
    code_cells += 1
    for output in cell.get("outputs", []):
        if output.get("output_type") == "error":
            errors.append(f"cell {index}: {output.get('ename')}: {output.get('evalue')}")

if code_cells == 0:
    raise SystemExit(f"No code cells found in {executed_notebook}")
if errors:
    raise SystemExit("Qtenon baked notebook cache contains errors: " + "; ".join(errors))

metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
print(
    "Qtenon baked notebook cache passed "
    f"({code_cells} code cells, built_at={metadata.get('built_at_utc', '<unknown>')})"
)
PY
}
