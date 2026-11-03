#!/usr/bin/env python3
"""Fetch immutable GitHub archives, verify hashes, apply narrow packaging edits."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
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
    # A downstream upload gets its own changelog entry. Preserve the upstream
    # maintainer's version and history rather than rewriting their entry.
    changelog = dest / "debian/changelog"
    text = changelog.read_text()
    first = re.match(r"(\S+) \(([^)]+)\)", text)
    if not first:
        raise SystemExit(f"Invalid upstream changelog: {name}")
    version = first[2] + "+" + lock["local_revision"]
    date = format_datetime(datetime.now(timezone.utc))
    entry = (f"{first[1]} ({version}) unstable; urgency=medium\n\n"
             "  * Downstream minimal build; remove documented optional online integrations.\n\n"
             f" -- Deepin Lite Builder <builder@localhost>  {date}\n\n")
    changelog.write_text(entry + text, encoding="utf-8", newline="\n")
    print(f"Prepared {name} @ {source['commit']}")
