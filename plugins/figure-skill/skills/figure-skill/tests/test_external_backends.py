from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ExternalBackendBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = load_module("external_backend_bootstrap", SCRIPTS / "bootstrap_external_backends.py")
        cls.paths = load_module("external_runtime_paths", SCRIPTS / "adapters" / "external_runtime.py")

    def test_pinned_backend_contracts(self):
        self.assertEqual(
            self.bootstrap.BACKENDS["paperbanana"]["commit"],
            "836455537e863b5a2f40dace487a782c0bc5ef94",
        )
        self.assertEqual(
            self.bootstrap.BACKENDS["autofigure-edit"]["commit"],
            "16f3749e9d512bdf7b7b55c162307bc289750b7a",
        )

    def test_bootstrap_and_adapters_share_versioned_runtime_paths(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"FIGURE_SKILL_RUNTIME_ROOT": temp}, clear=False
        ):
            bootstrap_paths = self.bootstrap.paths_for("autofigure-edit")
            adapter_paths = self.paths.backend_paths("autofigure-edit")
            self.assertEqual(bootstrap_paths["repo"], adapter_paths["repo"])
            self.assertEqual(bootstrap_paths["python"], adapter_paths["python"])
            self.assertIn(self.bootstrap.plugin_version(), str(bootstrap_paths["repo"]))

    def test_backend_status_requires_repo_python_entrypoint_and_commit(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"FIGURE_SKILL_RUNTIME_ROOT": temp}, clear=False
        ):
            paths = self.bootstrap.paths_for("paperbanana")
            paths["repo"].mkdir(parents=True)
            paths["python"].parent.mkdir(parents=True)
            paths["python"].touch()
            paths["entrypoint"].parent.mkdir(parents=True, exist_ok=True)
            paths["entrypoint"].touch()
            requirements = paths["repo"] / "requirements.txt"
            requirements.write_text("example==1.0\n", encoding="utf-8")
            expected = self.bootstrap.BACKENDS["paperbanana"]["commit"]
            paths["marker"].write_text(json.dumps({
                "schema_version": "1.0", "backend": "paperbanana", "commit": expected,
                "requirements_sha256": self.bootstrap.sha256(requirements),
                "python": str(paths["python"]),
            }), encoding="utf-8")
            with mock.patch.object(self.bootstrap, "current_commit", return_value=expected):
                self.assertTrue(self.bootstrap.backend_status("paperbanana")["ready"])

    def test_install_lock_rejects_concurrent_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"FIGURE_SKILL_RUNTIME_ROOT": temp}, clear=False
        ):
            lock = self.bootstrap.acquire_lock()
            try:
                with self.assertRaisesRegex(RuntimeError, "another backend installation"):
                    self.bootstrap.acquire_lock()
            finally:
                lock.unlink(missing_ok=True)

    def test_plugin_packages_three_skills_and_team_installer(self):
        plugin_root = SKILL.parents[1]
        repo_root = SKILL.parents[3]
        self.assertTrue((plugin_root / "skills" / "figure-skill" / "SKILL.md").is_file())
        self.assertTrue((plugin_root / "skills" / "paperbanana" / "SKILL.md").is_file())
        self.assertTrue((plugin_root / "skills" / "autofigure-edit" / "SKILL.md").is_file())
        self.assertTrue((repo_root / "scripts" / "install_team.ps1").is_file())


if __name__ == "__main__":
    unittest.main()
