from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from git_agent import __version__
from git_agent.git_ops import (
    get_current_branch,
    git_status_porcelain,
    has_commits,
    has_remote_origin,
    has_staged_changes,
    is_git_repo,
    run_git,
    suggest_error_fix,
)


def log(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def ask_yes_no(prompt: str, default: str = "y", auto: bool = False) -> bool:
    if auto:
        return True
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


def format_git_argv(argv: list[str]) -> str:
    return "git " + " ".join(shlex.quote(a) for a in argv)


def run_git_step(title: str, argv: list[str], auto: bool, verbose: bool) -> tuple[bool, bool]:
    """
    Run one git invocation with optional confirmation.

    Returns (continue_workflow, command_succeeded). If the user declines the step
    or chooses not to continue after an error, continue_workflow is False.
    command_succeeded is False when git exited non-zero (even if the user chose
    to continue the workflow).
    """
    print()
    print("=" * 72)
    print(title)
    print(f"  {format_git_argv(argv)}")
    log(verbose, f"[git-agent] cwd={Path.cwd()}")

    if not ask_yes_no("Run this command?", default="y", auto=auto):
        print("Stopped: this step was declined.")
        return False, False

    code, stdout, stderr = run_git(argv)
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    if code != 0:
        print(f"Error: command failed (exit code {code}).", file=sys.stderr)
        print(f"Suggested fix: {suggest_error_fix(stderr)}", file=sys.stderr)
        if not ask_yes_no("Continue with the remaining steps anyway?", default="n", auto=False):
            return False, False
        return True, False

    print("Success.")
    return True, True


def ensure_origin_remote(auto: bool, verbose: bool) -> bool:
    """Configure `origin` using a repository URL pasted by the user (HTTPS or SSH)."""
    if has_remote_origin():
        log(verbose, "[git-agent] origin remote already present.")
        print("\nUsing existing `origin` remote.")
        return True

    print("\nCreate an empty repository on GitHub (github.com → New repository), then paste its URL below.")

    while True:
        url = input(
            "\nPaste repository clone URL (HTTPS or SSH). Leave empty to cancel:\n> "
        ).strip()
        if not url:
            print("Cancelled: no origin remote configured.", file=sys.stderr)
            return False

        if has_remote_origin():
            argv = ["remote", "set-url", "origin", url]
            label = "Update origin URL"
        else:
            argv = ["remote", "add", "origin", url]
            label = "Add origin remote"

        proceed, _ = run_git_step(label, argv, auto, verbose)
        if not proceed:
            continue

        if has_remote_origin():
            _, configured, _ = run_git(["remote", "get-url", "origin"])
            if configured:
                log(verbose, f"[git-agent] origin -> {configured}")
            return True

        print("origin is still missing. Try another URL.", file=sys.stderr)


def cmd_push(args: argparse.Namespace) -> int:
    auto = bool(args.yes)
    verbose = bool(args.verbose)

    print("git-agent push")
    print("-" * 72)

    if not is_git_repo():
        proceed, _ok = run_git_step("Initialize Git repository", ["init"], auto, verbose)
        if not proceed:
            return 1
        if not is_git_repo():
            print("Still not a Git repository after git init.", file=sys.stderr)
            return 1

    if git_status_porcelain():
        proceed, _ok = run_git_step("Stage all changes", ["add", "."], auto, verbose)
        if not proceed:
            return 1

    need_commit = (not has_commits()) or bool(git_status_porcelain()) or has_staged_changes()
    if need_commit:
        if not has_commits() and not has_staged_changes() and not git_status_porcelain():
            commit_argv = ["commit", "--allow-empty", "-m", "Initial commit"]
        else:
            commit_argv = ["commit", "-m", "Initial commit"]
        proceed, _ok = run_git_step("Create commit", commit_argv, auto, verbose)
        if not proceed:
            return 1

    branch = get_current_branch()
    if branch != "main":
        proceed, _ok = run_git_step("Rename branch to main", ["branch", "-M", "main"], auto, verbose)
        if not proceed:
            return 1

    if not ensure_origin_remote(auto, verbose):
        return 1

    proceed, pushed = run_git_step("Push to GitHub", ["push", "-u", "origin", "main"], auto, verbose)
    if not proceed:
        return 1

    print()
    print("=" * 72)
    if pushed:
        print("Done. Your project is pushed to GitHub (branch main, upstream set).")
        return 0

    print(
        "Push did not complete successfully. Fix the problem (see below), then run "
        "`git push -u origin main` again.",
        file=sys.stderr,
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-agent",
        description="Push the current project directory to GitHub with guided Git steps.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    push_p = sub.add_parser("push", help="Initialize, commit, set origin from URL, and push.")
    push_p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto mode: run Git commands without confirmation (you still paste the repo URL).",
    )
    push_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print extra diagnostics to stderr.",
    )
    push_p.set_defaults(func=cmd_push)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
