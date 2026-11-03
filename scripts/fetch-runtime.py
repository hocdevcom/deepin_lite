#!/usr/bin/env python3
"""Fetch the explicitly locked local-authentication runtime, without a repo enable."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
from image_cleanup import audit

base = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for item in json.loads((base / "config/required-runtime.json").read_text()):
    path = out / (item["package"] + ".deb")
    with urllib.request.urlopen(item["url"], timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise SystemExit("Runtime checksum mismatch: " + item["package"])
    path.write_bytes(data)
    for field in ("package", "version"):
        actual = subprocess.check_output(["dpkg-deb", "-f", str(path), field.title()], text=True).strip()
        if actual != item[field]:
            raise SystemExit("Unexpected runtime " + field + ": " + actual)
    with tempfile.TemporaryDirectory(prefix="deepin-auth-audit-") as tmp:
        root = Path(tmp)
        subprocess.run(["dpkg-deb", "-x", str(path), tmp], check=True)
        subprocess.run(["dpkg-deb", "-e", str(path), str(root / "DEBIAN")], check=True)
        hits = audit(root)
        if hits:
            raise SystemExit("Required local runtime failed online-integration audit: " + "; ".join(hits))
    print("Verified local authentication runtime: " + item["package"] + " " + item["version"])
