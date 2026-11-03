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
        for name in ["libasyncns0", "systemd-timesyncd", "rsync", "dde-daemon", "deepin-terminal"]:
            with self.subTest(name=name):
                self.assertFalse(policy.forbidden(name, patterns))

    def test_manifest_audit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "packages.tsv"
            for content, expected in [("", False), ("uos-ai\t1.0\t42\n", False), ("dde-daemon\t6.0\t42\n", True)]:
                manifest.write_text(content)
                result = subprocess.run([sys.executable, "scripts/policy.py", "audit", "--manifest", str(manifest)], cwd=ROOT, capture_output=True)
                self.assertEqual(result.returncode == 0, expected)


if __name__ == "__main__":
    unittest.main()
