#!/usr/bin/env python3
"""Resolve critical ELF relocations inside the image after rebuilding shared APIs."""
from pathlib import Path
import subprocess
import sys

root, report = map(Path, sys.argv[1:])
paths = ["usr/bin/" + name for name in (
    "dde-shell", "dde-desktop", "dde-appearance", "dde-session", "dde-control-center",
    "dde-lock", "lightdm-deepin-greeter", "deepin-terminal", "deepin-kwin_x11")]
paths += [p.relative_to(root).as_posix()
          for p in (root / "usr/libexec/dde-file-manager").glob("*") if p.is_file()]
for pattern in ("libdtkwidget.so.5.*", "libdtk6widget.so.6.*", "libdframeworkdbus.so.2.*"):
    libraries = list((root / "usr/lib/x86_64-linux-gnu").glob(pattern))
    if not libraries:
        raise SystemExit("Missing rebuilt runtime library: " + pattern)
    paths += [p.relative_to(root).as_posix() for p in libraries]
results, failures = [], []
for relative in sorted(set(paths)):
    path = root / relative
    if not path.is_file():
        raise SystemExit("Missing critical executable: " + relative)
    with path.open("rb") as source:
        if source.read(4) != b"\x7fELF":
            continue  # Shell launchers are verified by the subsequent boot test.
    result = subprocess.run(["chroot", str(root), "ldd", "-r", "/" + relative],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if "not a dynamic executable" in result.stdout:
        continue
    bad = result.returncode != 0 or "not found" in result.stdout or "undefined symbol:" in result.stdout
    results.append(("FAIL: " if bad else "PASS: ") + relative + "\n" + result.stdout)
    if bad:
        failures.append(relative)
report.write_text("\n".join(results), encoding="utf-8")
if failures:
    raise SystemExit("Runtime link audit failed: " + ", ".join(failures))
print(f"PASS: resolved critical ELF dependencies and symbols in {len(results)} targets")
