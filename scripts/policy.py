#!/usr/bin/env python3
"""One policy implementation for APT pins and installed-package audits."""
import argparse
import fnmatch
from pathlib import Path


def lines(path):
    return [s for line in Path(path).read_text(encoding="utf-8").splitlines()
            if (s := line.split("#", 1)[0].strip())]


def forbidden(name, patterns):
    return any(fnmatch.fnmatchcase(name.split(":", 1)[0], p) for p in patterns)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["pins", "audit", "validate"])
    p.add_argument("--deny", default="config/deny-packages.txt")
    p.add_argument("--packages", default="config/packages.txt")
    p.add_argument("--manifest")
    a = p.parse_args()
    patterns = lines(a.deny)
    if a.action == "pins":
        print("Package: " + " ".join(patterns))
        print("Pin: version *\nPin-Priority: -1\n")
    elif a.action == "validate":
        bad = [n for n in lines(a.packages) if forbidden(n, patterns)]
        if bad:
            raise SystemExit("Requested packages denied: " + ", ".join(bad))
    else:
        if not a.manifest:
            p.error("--manifest required")
        names = [line.split()[0] for line in Path(a.manifest).read_text().splitlines() if line.strip()]
        if not names:
            raise SystemExit("Empty package manifest")
        bad = [n for n in names if forbidden(n, patterns)]
        if bad:
            raise SystemExit("Forbidden packages in image: " + ", ".join(bad))
        print(f"PASS: {len(names)} installed packages checked against {len(patterns)} rules")


if __name__ == "__main__":
    main()
