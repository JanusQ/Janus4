#!/usr/bin/env python3
"""Execute the tutorial notebook end-to-end and print per-cell timings."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time

import nbformat
from nbclient import NotebookClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notebook",
        type=Path,
        default=Path(__file__).with_name("qtenon_tutorial.ipynb"),
        help="Notebook to execute.",
    )
    parser.add_argument(
        "--kernel",
        default="qtenon",
        help="Kernel name to use for execution.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-cell timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("qtenon_tutorial.executed.ipynb"),
        help="Where to write the executed notebook copy.",
    )
    return parser.parse_args()


def output_line_count(cell: nbformat.NotebookNode) -> int:
    total = 0
    for output in cell.get("outputs", []):
        if "text" in output:
            total += len("".join(output["text"]).splitlines())
        elif "data" in output and "text/plain" in output["data"]:
            total += len("".join(output["data"]["text/plain"]).splitlines())
    return total


def execution_seconds(cell: nbformat.NotebookNode) -> float | None:
    execution = cell.get("metadata", {}).get("execution", {})
    busy = execution.get("iopub.status.busy")
    idle = execution.get("iopub.status.idle")
    if not busy or not idle:
        return None
    busy_dt = datetime.fromisoformat(busy.replace("Z", "+00:00"))
    idle_dt = datetime.fromisoformat(idle.replace("Z", "+00:00"))
    return (idle_dt - busy_dt).total_seconds()


def main() -> int:
    args = parse_args()
    notebook_path = args.notebook.resolve()
    notebook = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=args.timeout,
        kernel_name=args.kernel,
        record_timing=True,
        allow_errors=False,
    )

    started = time.perf_counter()
    executed = client.execute(cwd=str(notebook_path.parent))
    total_seconds = time.perf_counter() - started

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(nbformat.writes(executed), encoding="utf-8")

    print(f"NOTEBOOK {notebook_path}")
    print(f"EXECUTED_COPY {args.output}")
    print(f"TOTAL_SECONDS {total_seconds:.3f}")
    for index, cell in enumerate(executed.cells):
        if cell.cell_type != "code":
            continue
        first = "".join(cell.source).strip().splitlines()
        head = first[0] if first else "<empty>"
        print(
            "CELL",
            index,
            "SECONDS",
            execution_seconds(cell),
            "OUTPUT_LINES",
            output_line_count(cell),
            "HEAD",
            head[:90],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
