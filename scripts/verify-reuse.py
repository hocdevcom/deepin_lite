#!/usr/bin/env python3
"""Permit ISO-only retries using fully tested package artifacts from this repo."""
import json
import os
from pathlib import Path
import re
import urllib.request

run_ids = os.environ["PACKAGE_RUN_ID"].split(",")
if not all(re.fullmatch(r"[0-9]+", value) for value in run_ids):
    raise SystemExit("Invalid package workflow run ID")
repo = os.environ["GITHUB_REPOSITORY"]
token = os.environ["GH_TOKEN"]


def api(path):
    request = urllib.request.Request("https://api.github.com/repos/" + repo + path,
                                    headers={"Authorization": "Bearer " + token,
                                             "Accept": "application/vnd.github+json",
                                             "User-Agent": "deepin-lite-build-verifier"})
    return json.load(urllib.request.urlopen(request, timeout=60))


lock = json.loads(Path("config/upstream.lock.json").read_text())
expected = {"packages (" + source["repository"].rsplit("/", 1)[-1] + ")"
            for source in lock["sources"]}
passed = set()
for run_id in run_ids:
    jobs = api("/actions/runs/" + run_id + "/jobs?per_page=100")["jobs"]
    passed |= {job["name"] for job in jobs if job["status"] == "completed" and job["conclusion"] == "success"}
if not expected <= passed:
    raise SystemExit("Cannot reuse packages: missing successful jobs " + ", ".join(sorted(expected - passed)))
print("Verified successful package jobs across runs " + ",".join(run_ids))
print("Source archive content must additionally match freshly prepared current sources.")
