"""Read-only pin/bootstrap checks for the separately authorized Linux job."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_pin(path, commit, deadline=None):
    def timeout():
        remaining = 10 if deadline is None else min(10, deadline - time.monotonic())
        require(remaining > 0, "shared validation deadline exhausted")
        return remaining
    require(path.is_absolute() and path.is_dir() and re.fullmatch(r"[0-9a-f]{40}", commit), "absolute source and full pin required")
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, timeout=timeout()).strip()
    require(actual == commit, "source pin mismatch")
    require(not subprocess.check_output(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"], text=True, timeout=timeout()), "source not clean")


def bootstrap_ready(pstack, bun):
    require(bun.is_absolute() and bun.is_file() and os.access(bun, os.X_OK), "preinstalled Bun required")
    scripts = pstack / "pstack/skills/poteto-mode/scripts"
    key = hashlib.sha256((scripts / "package.json").read_bytes() + b"\0" + (scripts / "bun.lock").read_bytes()).hexdigest()
    modules = scripts / "node_modules"
    require((modules / "commander/package.json").is_file(), "preprovision commander; job will not install it")
    require((modules / ".poteto-mode-tools-install-key").read_text().strip() == key, "bootstrap install key mismatch; job will not install")
    return {"bootstrap_key": key, "commander_sha256": digest(modules / "commander/package.json"), "bun_sha256": digest(bun)}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
