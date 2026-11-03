from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_cleanup import clean_api


@unittest.skipUnless(shutil.which("make"), "GNU make required; runs on Linux CI")
class ParallelPrepareTest(unittest.TestCase):
    def test_binary_waits_for_source_preparation_under_parallel_make(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text(
                "all: build-binary\n"
                "build-binary: prepare out/bin/device\n"
                "prepare:\n"
                "\tsleep 0.2\n"
                "\tmkdir -p out/bin\n"
                "\ttouch source-ready\n"
                "out/bin/%:\n"
                "\ttest -f source-ready\n"
                "\ttouch $@\n", encoding="utf-8", newline="\n")
            clean_api(root)
            result = subprocess.run(["make", "-j2"], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / "out/bin/device").is_file())


if __name__ == "__main__":
    unittest.main()
