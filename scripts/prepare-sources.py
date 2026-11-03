#!/usr/bin/env python3
"""Fetch immutable GitHub archives, verify hashes, apply narrow packaging edits."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import urllib.request
from source_cleanup import clean_source

base = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
lock = json.loads((base / "config/upstream.lock.json").read_text())
for source in lock["sources"]:
    name = source["repository"].rsplit("/", 1)[-1]
    archive = out / (name + ".tar.gz")
    with urllib.request.urlopen(source["url"], timeout=120) as response:
        archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != source["sha256"]:
        raise SystemExit(f"Source checksum mismatch: {name}")
    dest = out / name
    dest.mkdir()
    with tarfile.open(archive) as tf:
        # Python's data filter rejects absolute paths and links escaping dest.
        for member in tf.getmembers():
            parts = member.name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            member.name = parts[1]
            tf.extract(member, dest, filter="data")
    archive.unlink()
    clean_source(name, dest)
    if name == "dde-api":
        control = dest / "debian/control"
        text = control.read_text()
        for font in ("fonts-noto-cjk", "fonts-unifont"):
            text, count = re.subn(r"(?m)^ " + re.escape(font) + r",\s*\n", "", text)
            if count != 1:
                raise SystemExit(f"Packaging changed; expected one {font} dependency")
        control.write_text(text)
    # Local version ensures APT chooses this patched build over upstream.
    changelog = dest / "debian/changelog"
    text = changelog.read_text()
    text = re.sub(r"\(([^)]+)\)", lambda m: "(" + m[1] + "+lite2)", text, count=1)
    changelog.write_text(text)
    print(f"Prepared {name} @ {source['commit']}")
