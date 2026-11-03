#!/usr/bin/env python3
"""Remove named online payloads, then reject known integration markers.

Never follows symlinks or touches host paths outside the explicit image root.
The audit is deliberately bounded to known identifiers; it is not a proof about
every possible implementation of AI, cloud or network behavior.
"""
import argparse
import os
from pathlib import Path
import re
import shutil

NAMES = re.compile(r"aiassistant|uos[-_.]ai|deepin[-_.](?:ai|cloud|sync)|deepinid|union[-_]?id|uadp|org\.deepin\.dde\.eventlog|(?:com|org)\.deepin\.(?:dde\.)?sync", re.I)
IDENTIFIERS = (
    "com.iflytek.aiassistant", "com.deepin.sync", "org.deepin.dde.sync",
    "com.deepin.deepinid", "org.deepin.dde.deepinid", "com.deepin.unionid",
    "org.deepin.dde.unionid", "org.deepin.dde.uadp", "org.deepin.dde.eventlog",
)
MARKERS = tuple((name, name.encode(encoding)) for name in IDENTIFIERS
                for encoding in ("ascii", "utf-16-le", "utf-16-be"))


def entries(root):
    for relative in ("etc", "usr", "opt"):
        start = root / relative
        if not start.is_dir() or start.is_symlink():
            continue
        for directory, dirs, files in os.walk(start, followlinks=False):
            for name in dirs + files:
                yield Path(directory) / name


def clean(root):
    deleted = []
    for path in list(entries(root)):
        if NAMES.search(path.name) and (path.is_symlink() or path.exists()):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            deleted.append(path.relative_to(root).as_posix())
    return deleted


def audit(root):
    failures = []
    overlap = max(len(marker) for _, marker in MARKERS) - 1
    for path in entries(root):
        relative = path.relative_to(root).as_posix()
        if NAMES.search(path.name):
            failures.append(f"payload: {relative}")
        if path.is_symlink() or not path.is_file():
            continue
        # Do not treat copyright/license history or translated labels as code.
        if relative.startswith(("usr/share/doc/", "usr/share/locale/", "usr/share/licenses/")):
            continue
        with path.open("rb") as source:
            tail = b""
            while chunk := source.read(1024 * 1024):
                data = (tail + chunk).lower()
                hit = next((name for name, marker in MARKERS if marker in data), None)
                if hit:
                    failures.append(f"integration {hit}: {relative}")
                    break
                tail = data[-overlap:]
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve(strict=True)
    if root == Path(root.anchor) or not (root / "var/lib/dpkg/status").is_file():
        parser.error("Expected a dedicated debootstrapped image root")
    deleted = clean(root)
    failures = audit(root)
    report = ["Physically removed payloads:", *deleted,
              f"Known-identifier audit: {'FAIL' if failures else 'PASS'}", *failures]
    Path(args.report).write_text("\n".join(report) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit("Residual online integrations found; see " + args.report)
    print(f"PASS: {len(deleted)} residual payload files removed; known-identifier audit passed")


if __name__ == "__main__":
    main()
