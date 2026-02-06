#!/usr/bin/env python3
"""Repo-local wrapper for the workflow agentctl implementation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    target = repo_root / ".codex" / "skills" / "vibe-loop" / "scripts" / "agentctl.py"
    if not target.exists():
        print(f"ERROR: fallback agentctl not found: {target}", file=sys.stderr)
        return 2

    cmd = [sys.executable, str(target), *sys.argv[1:]]
    completed = subprocess.run(cmd)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
