#!/usr/bin/env python3
"""Select packages for physical purging and audit the final installed set."""
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
    p.add_argument("action", choices=["purge-list", "audit", "validate", "check-purge"])
    p.add_argument("--deny", default="config/deny-packages.txt")
    p.add_argument("--packages", default="config/packages.txt")
    p.add_argument("--manifest")
    p.add_argument("--require")
    a = p.parse_args()
    patterns = lines(a.deny)
    if a.action == "check-purge":
        if not a.manifest:
            p.error("--manifest must contain the APT simulation output")
        removed = {fields[1].split(":", 1)[0]
                   for line in Path(a.manifest).read_text().splitlines()
                   if len(fields := line.split()) > 1 and fields[0] in {"Remv", "Purg"}}
        protected = set(lines(a.require or a.packages))
        if bad := removed & protected:
            raise SystemExit("Purge would remove required packages: " + ", ".join(sorted(bad)))
        print(f"PASS: purge plan preserves all {len(protected)} required packages")
        return
    if a.action == "validate":
        bad = [n for n in lines(a.packages) if forbidden(n, patterns)]
        if bad:
            raise SystemExit("Requested packages denied: " + ", ".join(bad))
    else:
        if not a.manifest:
            p.error("--manifest required")
        names = [line.split()[0] for line in Path(a.manifest).read_text().splitlines() if line.strip()]
        bad = [n for n in names if forbidden(n, patterns)]
        if a.action == "purge-list":
            print("\n".join(bad))
            return
        if not names:
            raise SystemExit("Empty package manifest")
        if bad:
            raise SystemExit("Forbidden packages in image: " + ", ".join(bad))
        if a.require:
            installed = {n.split(":", 1)[0] for n in names}
            missing = set(lines(a.require)) - installed
            if missing:
                raise SystemExit("Required desktop packages removed: " + ", ".join(sorted(missing)))
        print(f"PASS: {len(names)} installed packages checked against {len(patterns)} rules")


if __name__ == "__main__":
    main()
