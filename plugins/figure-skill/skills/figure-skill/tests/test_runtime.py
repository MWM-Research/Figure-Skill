from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = SKILL / "scripts" / "figure.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("figure_launcher", LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class RuntimeLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = load_launcher()

    def test_runtime_is_versioned_and_can_be_redirected(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"FIGURE_SKILL_RUNTIME_ROOT": temp}, clear=False
        ):
            expected = Path(temp).resolve() / self.launcher.plugin_version()
            self.assertEqual(self.launcher.runtime_dir(), expected)

    def test_ready_runtime_requires_matching_lock_hash(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"FIGURE_SKILL_RUNTIME_ROOT": temp}, clear=False
        ):
            root = self.launcher.runtime_dir()
            python = self.launcher.runtime_python(root)
            python.parent.mkdir(parents=True)
            python.touch()
            self.launcher.marker_path(root).write_text(
                json.dumps({
                    "version": self.launcher.plugin_version(),
                    "requirements_sha256": self.launcher.lock_digest(),
                }),
                encoding="utf-8",
            )
            self.assertTrue(self.launcher.runtime_ready())
            self.launcher.marker_path(root).write_text("{}", encoding="utf-8")
            self.assertFalse(self.launcher.runtime_ready())

    def test_dependencies_are_fully_pinned(self):
        lines = [
            line.strip() for line in (SKILL / "requirements-lock.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertGreater(len(lines), 10)
        self.assertTrue(all("==" in line for line in lines))

    def test_skill_uses_cwd_independent_launcher(self):
        instructions = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("python scripts/", instructions)
        self.assertIn("<SKILL_ROOT>/scripts/figure.py", instructions)


if __name__ == "__main__":
    unittest.main()
