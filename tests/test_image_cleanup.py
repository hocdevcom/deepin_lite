import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cleanup", ROOT / "scripts/image_cleanup.py")
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class ImageCleanupTest(unittest.TestCase):
    def test_payload_is_deleted_and_neutral_name_integration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "usr/lib/unionid").mkdir(parents=True)
            (root / "usr/lib/unionid/plugin.so").write_bytes(b"online plugin")
            (root / "usr/lib/local-sync.so").write_bytes(b"ordinary local synchronization")
            binary = root / "usr/lib/desktop-core.so"
            # Marker straddles the reader's 1 MiB boundary and uses Qt UTF-16.
            binary.write_bytes(b"x" * (1024 * 1024 - 8) + "com.deepin.sync.Helper".encode("utf-16-le"))
            deleted = cleanup.clean(root)
            self.assertIn("usr/lib/unionid", deleted)
            self.assertFalse((root / "usr/lib/unionid").exists())
            self.assertTrue((root / "usr/lib/local-sync.so").exists())
            self.assertTrue(any("desktop-core.so" in s for s in cleanup.audit(root)))
            binary.write_bytes(b"local desktop implementation")
            self.assertEqual(cleanup.audit(root), [])


if __name__ == "__main__":
    unittest.main()
