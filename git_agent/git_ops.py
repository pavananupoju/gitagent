from __future__ import annotations

import subprocess
from typing import List, Optional, Tuple


def run_git(argv: List[str]) -> Tuple[int, str, str]:
    completed = subprocess.run(
        ["git", *argv],
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def run_command(command: str) -> Tuple[int, str, str]:
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def is_git_repo() -> bool:
    code, _, _ = run_command("git rev-parse --is-inside-work-tree")
    return code == 0


def get_current_branch() -> Optional[str]:
    code, out, _ = run_command("git branch --show-current")
    if code == 0 and out:
        return out
    return None


def has_remote_origin() -> bool:
    code, _, _ = run_command("git remote get-url origin")
    return code == 0


def git_status_porcelain() -> str:
    code, out, _ = run_command("git status --porcelain")
    if code != 0:
        return ""
    return out.strip()


def has_commits() -> bool:
    code, _, _ = run_command("git rev-parse --verify HEAD")
    return code == 0


def has_staged_changes() -> bool:
    code, _, _ = run_command("git diff --cached --quiet")
    return code != 0


def suggest_error_fix(stderr: str) -> str:
    message = stderr.lower()

    if "not a git repository" in message:
        return "git init"
    if "please tell me who you are" in message or "unable to auto-detect email address" in message:
        return 'git config --global user.email "you@example.com"'
    if "src refspec" in message and "does not match any" in message:
        return 'git commit -m "Initial commit"'
    if "failed to push some refs" in message and "non-fast-forward" in message:
        return "git pull --rebase origin main"
    if "repository not found" in message:
        return "git remote -v"
    if "permission denied (publickey)" in message:
        return "ssh -T git@github.com"
    if "authentication failed" in message:
        return "git ls-remote origin"
    if "could not read from remote repository" in message:
        return "git remote -v"
    if "remote origin already exists" in message:
        return "git remote set-url origin <new-repo-url>"
    if "error: src refspec main does not match any" in message.lower():
        return 'git commit -m "Initial commit"'

    return "git status"
