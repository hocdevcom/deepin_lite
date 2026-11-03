#!/usr/bin/env python3
"""Audit rebuilt DEB payloads and maintainer scripts before runtime installation."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from image_cleanup import audit

parser = argparse.ArgumentParser()
parser.add_argument("directory")
parser.add_argument("--report", required=True)
parser.add_argument("--source", help="Audit one matrix source instead of the complete image set")
args = parser.parse_args()
base = Path(__file__).resolve().parent.parent
lock = json.loads((base / "config/upstream.lock.json").read_text())
expected = {s["repository"].rsplit("/", 1)[-1] for s in lock["sources"]}
if args.source:
    if args.source not in expected:
        parser.error("Unknown locked source")
    expected = {args.source}
seen = set()
failures = []
report = []
debs = sorted(Path(args.directory).glob("*.deb"))
if not debs:
    raise SystemExit("No rebuilt DEBs to audit")
for deb in debs:
    def field(name):
        return subprocess.check_output(["dpkg-deb", "-f", str(deb), name], text=True).strip()
    name, version, source = field("Package"), field("Version"), field("Source")
    seen.add((source or name).split()[0])
    if not version.endswith("+" + lock["local_revision"]):
        failures.append(f"{name}: unexpected downstream version {version}")
    with tempfile.TemporaryDirectory(prefix="deepin-deb-audit-") as tmp:
        root = Path(tmp)
        subprocess.run(["dpkg-deb", "--extract", str(deb), str(root)], check=True)
        subprocess.run(["dpkg-deb", "--control", str(deb), str(root / "DEBIAN")], check=True)
        hits = audit(root)
        failures.extend(f"{name}: {hit}" for hit in hits)
        report.append(f"{name} {version}: {'FAIL' if hits else 'PASS'}")
failures.extend("Missing runtime build for source: " + name for name in sorted(expected - seen))
Path(args.report).write_text("\n".join(report + failures) + "\n", encoding="utf-8")
if failures:
    raise SystemExit("Rebuilt DEB audit failed; see " + args.report)
print(f"PASS: payloads and maintainer scripts checked in {len(debs)} rebuilt DEBs")
