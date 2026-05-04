#!/usr/bin/env python3
"""Legacy entry point: use `git-agent push` after installation."""

from __future__ import annotations

import sys

from git_agent.cli import main


if __name__ == "__main__":
    argv = ["push", *sys.argv[1:]]
    raise SystemExit(main(argv))
