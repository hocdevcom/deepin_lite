#!/usr/bin/env python3
"""Require reused native source archives to match current downstream source content."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile


def relevant(name):
    path = Path(name)
    return path.name not in {".gitignore", ".gitattributes", ".gitreview", ".mailmap"} and not any(
        part in {".git", ".hg", ".svn", ".bzr", "CVS"} for part in path.parts)


def digest(name, data):
    if name == "debian/changelog":
        data = re.sub(rb"(?m)^ -- Deepin Lite Builder <builder@localhost>  .*$",
                      b" -- Deepin Lite Builder <builder@localhost>  BUILD_DATE", data)
    # Packaging on Linux and source preparation on Windows can differ in text
    # line endings. No other code/content differences are accepted.
    try:
        data.decode("utf-8")
        if b"\0" not in data:
            data = data.replace(b"\r\n", b"\n")
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(data).hexdigest()


def archive_files(archive):
    result = {}
    with tarfile.open(archive) as tf:
        for member in tf:
            parts = member.name.split("/", 1)
            if len(parts) != 2 or not parts[1] or not relevant(parts[1]):
                continue
            name = parts[1]
            if member.isfile():
                result[name] = digest(name, tf.extractfile(member).read())
            elif member.issym():
                result[name] = "link:" + member.linkname
    return result


def tree_files(root):
    result = {}
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        if not relevant(name):
            continue
        if path.is_symlink():
            result[name] = "link:" + str(path.readlink())
        elif path.is_file():
            result[name] = digest(name, path.read_bytes())
    return result


def main():
    lock = json.loads(Path("config/upstream.lock.json").read_text())
    with tempfile.TemporaryDirectory(prefix="deepin-expected-source-") as tmp:
        subprocess.run([sys.executable, "scripts/prepare-sources.py", tmp], check=True)
        for source in lock["sources"]:
            name = (source.get("name") or source["repository"].rsplit("/", 1)[-1])
            archives = list(Path("incoming/sources").glob(name + "_*.tar.*"))
            if len(archives) != 1:
                raise SystemExit("Expected one native source archive for " + name)
            actual, expected = archive_files(archives[0]), tree_files(Path(tmp) / name)
            changed = sorted(key for key in actual.keys() | expected.keys() if actual.get(key) != expected.get(key))
            if changed:
                raise SystemExit("Rebuild " + name + "; source content changed: " + ", ".join(changed[:20]))
            print("PASS: reused source content matches current patches: " + name)


if __name__ == "__main__":
    main()
