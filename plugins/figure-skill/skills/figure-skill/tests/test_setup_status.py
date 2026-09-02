from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


def load_capability():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("capability_cli_test", SCRIPTS / "capability_cli.py")
    module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module); return module


class SetupStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.capability = load_capability()

    def test_four_profiles_have_expected_backend_plans(self):
        expected = {"core": [], "vectorize": ["autofigure-edit"], "illustration": ["paperbanana"], "all": ["paperbanana", "autofigure-edit"]}
        for profile, backends in expected.items():
            plan = self.capability.install_plan(profile, recreate=False)
            self.assertEqual([item["backend"] for item in plan["actions"] if item["action"] == "install-backend"], backends)
            self.assertTrue(plan["credentials_are_never_written"])

    def test_dry_run_is_non_mutating_and_does_not_require_yes(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            environment = os.environ.copy(); environment["FIGURE_SKILL_RUNTIME_ROOT"] = str(runtime); environment["PYTHONUTF8"] = "1"
            result = subprocess.run([sys.executable, str(SCRIPTS / "figure.py"), "setup", "--profile", "all", "--dry-run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr); self.assertFalse(runtime.exists()); self.assertIn('"profile": "all"', result.stdout)

    def test_noninteractive_actual_setup_requires_profile_and_yes(self):
        for arguments in (("setup",), ("setup", "--profile", "core")):
            result = subprocess.run([sys.executable, str(SCRIPTS / "figure.py"), *arguments], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            self.assertEqual(result.returncode, 2); self.assertIn("requires", result.stderr)

    def test_status_matrix_distinguishes_missing_dependency_and_credential(self):
        backends = {
            "autofigure-edit": {"name": "autofigure-edit", "ready": True, "actual_commit": "abc", "marker_valid": True},
            "paperbanana": {"name": "paperbanana", "ready": False, "actual_commit": None, "marker_valid": False},
        }
        def credential(name): return {"available": name == "AUTOFIGURE_API_KEY", "scopes": ["process"] if name == "AUTOFIGURE_API_KEY" else []}
        with mock.patch.object(self.capability.launcher, "runtime_ready", return_value=True), mock.patch.object(self.capability.launcher, "runtime_dir", return_value=Path("runtime")), mock.patch.object(self.capability.launcher, "marker_path", return_value=Path("missing-marker")), mock.patch.object(self.capability.environment_check, "browser_path", return_value="browser"), mock.patch.object(self.capability.environment_check, "credential_status", side_effect=credential), mock.patch.object(self.capability.external, "backend_status", side_effect=lambda name: backends[name]):
            report = self.capability.capability_report()
        states = {item["id"]: item["status"] for item in report["capabilities"]}
        self.assertEqual(states["deterministic-plots"], "ready"); self.assertEqual(states["png-to-svg"], "ready"); self.assertEqual(states["paperbanana-illustration"], "missing-dependency"); self.assertEqual(states["byok-raster-illustration"], "missing-credential")

    def test_setup_core_writes_redacted_atomic_report_and_missing_keys_do_not_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = root / "report.json"
            report = {"schema_version": "1.0", "figure_skill_version": "test", "core_ready": True, "runtime": str(root), "capabilities": [{"id": key, "label": self.capability.CAPABILITY_LABELS[key], "status": "ready" if key in {"deterministic-plots", "native-svg", "hybrid-figure"} else "missing-credential", "details": {"required_credentials": ["KEY_NAME"]}} for key in self.capability.CAPABILITY_LABELS]}
            with mock.patch.object(self.capability.launcher, "bootstrap"), mock.patch.object(self.capability.launcher, "runtime_dir", return_value=root), mock.patch.object(self.capability, "capability_report", return_value=report):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = self.capability.setup_command(["--profile", "core", "--yes", "--output", str(output)])
            self.assertEqual(code, 0); text = output.read_text(encoding="utf-8"); self.assertIn("KEY_NAME", text); self.assertNotIn("secret-value", text); self.assertFalse(output.with_suffix(".json.tmp").exists())

    def test_require_profile_exit_codes(self):
        report = {"core_ready": True, "capabilities": [{"id": capability, "label": label, "status": "ready" if capability in self.capability.PROFILES["core"]["required"] else "missing-credential", "details": {}} for capability, label in self.capability.CAPABILITY_LABELS.items()]}
        with mock.patch.object(self.capability, "capability_report", return_value=report):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.capability.status_command(["--require-profile", "core", "--json"]), 0)
                self.assertEqual(self.capability.status_command(["--require-profile", "all", "--json"]), 2)


if __name__ == "__main__": unittest.main()
