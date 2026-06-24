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
run_root = Path("/workspace/2-qtenon/tutorial/runs")

required = [executed_notebook, metadata_path]
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
metadata_files = metadata.get("files", {})
if not isinstance(metadata_files, dict):
    raise SystemExit(f"Qtenon baked notebook cache metadata has no files object: {metadata_path}")

missing_from_metadata: list[str] = []
for raw_path in metadata_files:
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path("/workspace/2-qtenon") / path
    if not path.is_file():
        missing_from_metadata.append(raw_path)
if missing_from_metadata:
    raise SystemExit(
        "Qtenon baked notebook cache metadata references missing files: "
        + ", ".join(missing_from_metadata)
    )

optional_run_artifacts = 0
if run_root.exists():
    optional_run_artifacts = sum(1 for path in run_root.rglob("*") if path.is_file())

print(
    "Qtenon baked notebook cache passed "
    f"({code_cells} code cells, built_at={metadata.get('built_at_utc', '<unknown>')}, "
    f"optional_run_artifacts={optional_run_artifacts})"
)
PY
}
