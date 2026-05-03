#!/usr/bin/env python3
"""
GitHub Push Assistant Agent

A step-by-step CLI agent that:
- Suggests required git commands
- Asks for confirmation before each command
- Executes commands only with approval
- Detects common git push errors and suggests fixes
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class CommandStep:
    title: str
    command: str
    optional: bool = False


def run_command(command: str) -> Tuple[int, str, str]:
    """Run a shell command and return (exit_code, stdout, stderr)."""
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def ask_yes_no(prompt: str, default: str = "y") -> bool:
    """Prompt the user for yes/no response."""
    suffix = "[Y/n]" if default.lower() == "y" else "[y/N]"
    while True:
        value = input(f"{prompt} {suffix}: ").strip().lower()
        if not value:
            return default.lower() == "y"
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please enter y or n.")


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


def has_staged_or_unstaged_changes() -> bool:
    code, out, _ = run_command("git status --porcelain")
    return code == 0 and bool(out.strip())


def has_project_files() -> bool:
    """Detect whether current directory has files worth committing."""
    ignored_entries = {".git", "__pycache__"}
    for name in os.listdir("."):
        if name in ignored_entries:
            continue
        return True
    return False


def suggest_error_fix(stderr: str) -> str:
    message = stderr.lower()

    if "not a git repository" in message:
        return "Run `git init` first, then re-run this agent."
    if "please tell me who you are" in message or "unable to auto-detect email address" in message:
        return (
            "Set Git identity:\n"
            "  git config --global user.name \"Your Name\"\n"
            "  git config --global user.email \"you@example.com\""
        )
    if "src refspec" in message and "does not match any" in message:
        return (
            "No commits found or wrong branch name. Create a commit first and verify branch:\n"
            "  git add .\n"
            "  git commit -m \"Initial commit\"\n"
            "  git branch --show-current"
        )
    if "failed to push some refs" in message and "non-fast-forward" in message:
        return (
            "Remote has newer commits. Pull/rebase before pushing:\n"
            "  git pull --rebase origin <branch>\n"
            "Then push again."
        )
    if "repository not found" in message:
        return "Check the remote URL and repository permissions using `git remote -v`."
    if "permission denied (publickey)" in message:
        return (
            "SSH key issue. Add your SSH key to GitHub and test:\n"
            "  ssh -T git@github.com\n"
            "Or switch remote to HTTPS."
        )
    if "authentication failed" in message:
        return (
            "Authentication failed. Re-authenticate via Git Credential Manager or use a PAT for HTTPS."
        )
    if "could not read from remote repository" in message:
        return "Check network, remote URL, and access rights."
    if "remote origin already exists" in message:
        return (
            "Origin remote already exists. Update it if needed:\n"
            "  git remote set-url origin <new-repo-url>"
        )
    if "error: src refspec main does not match any" in message:
        return "Branch `main` may not exist yet. Check branch with `git branch --show-current`."

    return "Review the error text and run `git status` / `git remote -v` for diagnostics."


def execute_step(step: CommandStep) -> bool:
    print("\n" + "=" * 72)
    print(f"Step: {step.title}")
    print(f"Suggested command:\n  {step.command}")

    if not ask_yes_no("Do you want to execute this command?", default="y"):
        if step.optional:
            print("Skipped optional step.")
            return True
        print("Skipped required step. Stopping flow.")
        return False

    code, stdout, stderr = run_command(step.command)
    if stdout:
        print("\nOutput:")
        print(stdout)
    if stderr:
        print("\nError output:")
        print(stderr)

    if code != 0:
        print("\nCommand failed.")
        print("Suggested fix:")
        print(suggest_error_fix(stderr))
        return ask_yes_no("Do you want to continue to the next step anyway?", default="n")

    print("Command succeeded.")
    return True


def build_steps() -> List[CommandStep]:
    steps: List[CommandStep] = []
    repo_exists = is_git_repo()

    if not repo_exists:
        steps.append(CommandStep(title="Initialize Git repository", command="git init"))

    if not has_remote_origin():
        remote_url = input(
            "\nEnter your GitHub repository URL (HTTPS or SSH), e.g. https://github.com/user/repo.git:\n> "
        ).strip()
        while not remote_url:
            remote_url = input("Remote URL cannot be empty. Enter repository URL:\n> ").strip()
        steps.append(CommandStep(title="Add GitHub remote", command=f"git remote add origin {remote_url}"))
    else:
        print("\nDetected existing `origin` remote.")

    should_commit = has_staged_or_unstaged_changes() if repo_exists else has_project_files()
    if should_commit:
        steps.append(CommandStep(title="Stage all changes", command="git add ."))
        commit_message = input("\nEnter commit message [default: Initial commit]:\n> ").strip() or "Initial commit"
        steps.append(CommandStep(title="Create commit", command=f'git commit -m "{commit_message}"'))
    else:
        print("\nNo file changes detected for commit.")

    branch = get_current_branch()
    if not branch:
        branch = "main"
        steps.append(CommandStep(title="Create/switch branch to main", command="git branch -M main"))
    elif branch != "main":
        if ask_yes_no(f"\nCurrent branch is `{branch}`. Rename/switch to `main`?", default="n"):
            steps.append(CommandStep(title="Rename/switch branch to main", command="git branch -M main"))
            branch = "main"
    else:
        print("\nCurrent branch is `main`.")

    steps.append(CommandStep(title=f"Push to GitHub (origin/{branch})", command=f"git push -u origin {branch}"))

    return steps


def main() -> None:
    print("GitHub Push Assistant Agent")
    print("-" * 72)
    print("This agent will suggest each command and ask before running it.")

    steps = build_steps()
    if not steps:
        print("\nNo actions required.")
        return

    print(f"\nPrepared {len(steps)} step(s).")
    if not ask_yes_no("Start guided execution now?", default="y"):
        print("Exiting without running commands.")
        return

    for step in steps:
        should_continue = execute_step(step)
        if not should_continue:
            print("\nExecution stopped.")
            return

    print("\nAll planned steps completed.")
    print("Run `git status` to verify your repository state.")


if __name__ == "__main__":
    main()
