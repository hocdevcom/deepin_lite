#!/usr/bin/env python3
"""Collect package artifacts only from successful jobs, including ISO-only retries."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

repo = os.environ["GITHUB_REPOSITORY"]
token = os.environ["GH_TOKEN"]
runs = (os.environ.get("PACKAGE_RUN_ID") or os.environ["GITHUB_RUN_ID"]).split(",")
expected = {(source.get("name") or source["repository"].rsplit("/", 1)[-1])
            for source in json.loads(Path("config/upstream.lock.json").read_text())["sources"]}
out = Path("incoming")
out.mkdir(exist_ok=True)
collected = {}
for run_id in runs:
    if not re.fullmatch(r"[0-9]+", run_id):
        raise SystemExit("Invalid workflow run ID")
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100",
                                    headers={"Authorization": "Bearer " + token,
                                             "User-Agent": "deepin-lite-package-collector"})
    jobs = json.load(urllib.request.urlopen(request, timeout=60))["jobs"]
    good = {job["name"] for job in jobs if job["status"] == "completed" and job["conclusion"] == "success"}
    for name in sorted(expected):
        if "packages (" + name + ")" not in good:
            continue
        with tempfile.TemporaryDirectory(prefix="deepin-package-") as tmp:
            subprocess.run(["gh", "run", "download", run_id, "--repo", repo,
                            "--name", "deepin-package-" + name, "--dir", tmp], check=True)
            for path in Path(tmp).rglob("*"):
                if path.is_file():
                    relative = path.relative_to(tmp)
                    dest = out / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, dest)
        collected[name] = run_id
if expected - collected.keys():
    raise SystemExit("Missing package artifacts: " + ", ".join(sorted(expected - collected.keys())))
Path("package-provenance.json").write_text(json.dumps(collected, indent=2) + "\n")
