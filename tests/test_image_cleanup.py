import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cleanup", ROOT / "scripts/image_cleanup.py")
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class ImageCleanupTest(unittest.TestCase):
    def test_residual_payload_is_rejected_without_modifying_packaged_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "usr/lib/unionid").mkdir(parents=True)
            (root / "usr/lib/unionid/plugin.so").write_bytes(b"online plugin")
            (root / "usr/lib/local-sync.so").write_bytes(b"ordinary local synchronization")
            binary = root / "usr/lib/desktop-core.so"
            # Marker straddles the reader's 1 MiB boundary and uses Qt UTF-16.
            binary.write_bytes(b"x" * (1024 * 1024 - 8) + "com.deepin.sync.Helper".encode("utf-16-le"))
            self.assertTrue(any("unionid" in s for s in cleanup.audit(root)))
            self.assertTrue((root / "usr/lib/unionid/plugin.so").exists())
            self.assertTrue((root / "usr/lib/local-sync.so").exists())
            self.assertTrue(any("desktop-core.so" in s for s in cleanup.audit(root)))
            binary.write_bytes(b"local desktop implementation")
            self.assertFalse(any("desktop-core.so" in s for s in cleanup.audit(root)))
            self.assertFalse(any("local-sync.so" in s for s in cleanup.audit(root)))

    def test_local_key_storage_is_not_classified_as_cloud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "usr/lib").mkdir(parents=True)
            (root / "usr/lib/uadp.so").write_bytes(b"org.deepin.dde.Uadp1")
            self.assertEqual(cleanup.audit(root), [])


if __name__ == "__main__":
    unittest.main()
