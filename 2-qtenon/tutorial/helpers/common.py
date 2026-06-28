"""Shared paths, config names, and logging helpers for tutorial tooling."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path


@dataclass(frozen=True)
class TutorialPaths:
    """Resolved paths for the local `code/` tutorial repository."""

    repo_root: Path
    chipyard_config: Path
    tests_dir: Path
    tutorial_dir: Path
    helpers_dir: Path
    captures_dir: Path
    figures_dir: Path
    tools_dir: Path
    docs_dir: Path
    chipyard_root: Path
    config_name: str

    @classmethod
    def discover(cls, start: Path | None = None) -> "TutorialPaths":
        """Locate the `code/` repo root from this file or an arbitrary start path.

        ``chipyard_root`` and ``config_name`` are read from the environment
        (``QTENON_CHIPYARD_ROOT`` / ``QTENON_CONFIG_NAME``) so the notebook
        can target different chipyard checkouts without code edits.
        Defaults mirror a conventional local Chipyard checkout with
        ``QChipRocketConfig``.
        The laptop fallback path does not require ``chipyard_root`` to
        exist on disk — ``ensure_simulator`` raises ``ToolchainMissing``
        when the tree is absent.
        """

        anchor = (start or Path(__file__)).resolve()
        for candidate in (anchor, *anchor.parents):
            if (candidate / "README.md").is_file() and (candidate / "hw").is_dir() and (candidate / "software").is_dir():
                repo_root = candidate
                break
        else:
            raise FileNotFoundError("Could not locate the Qtenon tutorial `code/` repository root.")

        tutorial_dir = repo_root / "tutorial"
        chipyard_root = Path(
            os.environ.get(
                "QTENON_CHIPYARD_ROOT",
                str(Path.home() / "chipyard"),
            )
        ).expanduser()
        config_name = os.environ.get("QTENON_CONFIG_NAME", "QChipRocketConfig")
        return cls(
            repo_root=repo_root,
            chipyard_config=repo_root / "hw" / "qc" / "src" / "main" / "scala" / "config" / "RoCCAcceleratorConfigs.scala",
            tests_dir=repo_root / "software" / "tests",
            tutorial_dir=tutorial_dir,
            helpers_dir=tutorial_dir / "helpers",
            captures_dir=tutorial_dir / "captures",
            figures_dir=tutorial_dir / "figures",
            tools_dir=repo_root / "tools",
            docs_dir=repo_root / "docs",
            chipyard_root=chipyard_root,
            config_name=config_name,
        )

    @property
    def local_venv_python(self) -> Path:
        """Return the default interpreter inside the repo-local virtual environment."""

        return self.repo_root / ".venv" / "bin" / "python"


def get_logger(name: str = "qtenon_tutorial") -> logging.Logger:
    """Return a consistently formatted logger without duplicating handlers."""

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def ensure_directory(path: Path) -> Path:
    """Create a directory if needed and return it for fluent call sites."""

    path.mkdir(parents=True, exist_ok=True)
    return path
