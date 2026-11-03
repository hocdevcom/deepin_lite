import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("policy", ROOT / "scripts/policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTest(unittest.TestCase):
    def test_sensitive_packages_cannot_hide_behind_multiarch_or_suffix(self):
        patterns = policy.lines(ROOT / "config/deny-packages.txt")
        for name in ["uos-ai:amd64", "deepin-sync-daemon", "com.qq.im", "linglong-bin", "fcitx5-module-cloudpinyin"]:
            with self.subTest(name=name):
                self.assertTrue(policy.forbidden(name, patterns))
        for name in ["libasyncns0", "systemd-dev", "systemd-timesyncd", "rsync", "dde-daemon", "deepin-terminal", "deepin-installer", "deepin-installer-timezones", "spice-vdagent", "open-vm-tools-desktop"]:
            with self.subTest(name=name):
                self.assertFalse(policy.forbidden(name, patterns))

    def test_configured_packages_pass_policy_validation(self):
        result = subprocess.run([sys.executable, "scripts/policy.py", "validate"], cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))

    def test_manifest_audit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "packages.tsv"
            for content, expected in [("", False), ("uos-ai\t1.0\t42\n", False), ("dde-daemon\t6.0\t42\n", True)]:
                manifest.write_text(content)
                result = subprocess.run([sys.executable, "scripts/policy.py", "audit", "--manifest", str(manifest)], cwd=ROOT, capture_output=True)
                self.assertEqual(result.returncode == 0, expected)

    def test_purge_plan_preserves_required_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "purge-plan.txt"
            for content, expected in [("Purg deepin-sync [1.0]\n", True),
                                      ("Purg systemd-sysv:amd64 [255.2]\n", False),
                                      ("Remv dde-session [1.2]\n", False)]:
                plan.write_text(content)
                result = subprocess.run([sys.executable, "scripts/policy.py", "check-purge",
                                         "--manifest", str(plan)], cwd=ROOT, capture_output=True)
                self.assertEqual(result.returncode == 0, expected)


if __name__ == "__main__":
    unittest.main()
