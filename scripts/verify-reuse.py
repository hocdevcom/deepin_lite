#!/usr/bin/env python3
"""Permit ISO-only retries using fully tested package artifacts from this repo."""
import json
import os
from pathlib import Path
import re
import urllib.request

run_id = os.environ["PACKAGE_RUN_ID"]
if not re.fullmatch(r"[0-9]+", run_id):
    raise SystemExit("Invalid package workflow run ID")
repo = os.environ["GITHUB_REPOSITORY"]
token = os.environ["GH_TOKEN"]


def api(path):
    request = urllib.request.Request("https://api.github.com/repos/" + repo + path,
                                    headers={"Authorization": "Bearer " + token,
                                             "Accept": "application/vnd.github+json",
                                             "User-Agent": "deepin-lite-build-verifier"})
    return json.load(urllib.request.urlopen(request, timeout=60))


run = api("/actions/runs/" + run_id)
jobs = api("/actions/runs/" + run_id + "/jobs?per_page=100")["jobs"]
lock = json.loads(Path("config/upstream.lock.json").read_text())
expected = {"packages (" + source["repository"].rsplit("/", 1)[-1] + ")"
            for source in lock["sources"]}
passed = {job["name"] for job in jobs if job["status"] == "completed" and job["conclusion"] == "success"}
if not expected <= passed:
    raise SystemExit("Cannot reuse packages: missing successful jobs " + ", ".join(sorted(expected - passed)))
if run["head_sha"] != os.environ["GITHUB_SHA"]:
    comparison = api("/compare/" + run["head_sha"] + "..." + os.environ["GITHUB_SHA"])
    files = comparison.get("files", [])
    allowed = {".github/workflows/build.yml", "config/deepin-lite-smoke.service",
               "scripts/smoke.sh", "scripts/verify-reuse.py", "README.md",
               "docs/build-removal-review.md"}
    changed = {file["filename"] for file in files}
    changed |= {file["previous_filename"] for file in files if "previous_filename" in file}
    if len(files) >= 300 or changed - allowed:
        raise SystemExit("Source/recipe changed; rebuild packages instead of reusing artifacts: "
                         + ", ".join(sorted(changed - allowed)))
print(f"Verified package artifacts from run {run_id}, source commit {run['head_sha']}")
