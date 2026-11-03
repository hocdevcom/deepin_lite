#!/usr/bin/env python3
"""Apply the current runtime policy to fresh or reused DEB build outputs."""
from pathlib import Path
import shutil
import subprocess
import sys
from policy import forbidden, lines

source, destination = map(Path, sys.argv[1:])
destination.mkdir(parents=True, exist_ok=True)
patterns = lines("config/deny-packages.txt")
count = 0
for deb in sorted(source.glob("*.deb")):
    name = subprocess.check_output(["dpkg-deb", "-f", str(deb), "Package"], text=True).strip()
    if forbidden(name, patterns):
        print("Omit non-runtime package: " + name)
        continue
    shutil.copy2(deb, destination / deb.name)
    count += 1
if not count:
    raise SystemExit("No runtime DEBs selected")
print(f"Selected {count} runtime DEBs using the current policy")
