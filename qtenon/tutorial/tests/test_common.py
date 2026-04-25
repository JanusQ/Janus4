"""Unit tests for tutorial path and logging helpers."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from tutorial.helpers.common import TutorialPaths, get_logger


class TutorialPathsTest(unittest.TestCase):
    def test_discover_locates_repo_root(self) -> None:
        paths = TutorialPaths.discover(Path(__file__))
        self.assertTrue((paths.repo_root / "README.md").is_file())
        self.assertEqual(paths.captures_dir, paths.tutorial_dir / "captures")
        self.assertEqual(paths.figures_dir, paths.tutorial_dir / "figures")

    def test_logger_reuses_handlers(self) -> None:
        first = get_logger("qtenon_tutorial.tests.common")
        second = get_logger("qtenon_tutorial.tests.common")
        self.assertEqual(len(first.handlers), 1)
        self.assertIs(first.handlers[0], second.handlers[0])

    def test_chipyard_root_and_config_name_defaults(self) -> None:
        """Without env overrides, discover() still yields a Path + non-empty config name."""

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QTENON_CHIPYARD_ROOT", None)
            os.environ.pop("QTENON_CONFIG_NAME", None)
            paths = TutorialPaths.discover(Path(__file__))
        self.assertIsInstance(paths.chipyard_root, Path)
        self.assertEqual(paths.config_name, "QChipRocketConfig")
        # Default points inside chipyard checkout
        self.assertEqual(paths.chipyard_root.name, "chipyard")

    def test_chipyard_root_env_override(self) -> None:
        """Setting QTENON_CHIPYARD_ROOT / QTENON_CONFIG_NAME overrides defaults."""

        with mock.patch.dict(
            os.environ,
            {
                "QTENON_CHIPYARD_ROOT": "custom_ch",
                "QTENON_CONFIG_NAME": "CustomCfg",
            },
        ):
            paths = TutorialPaths.discover(Path(__file__))
        self.assertEqual(paths.chipyard_root, Path("custom_ch"))
        self.assertEqual(paths.config_name, "CustomCfg")


if __name__ == "__main__":
    unittest.main()
