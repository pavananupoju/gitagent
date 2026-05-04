from __future__ import annotations

import argparse
import os
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
from git_agent.github import create_user_repository, get_login, slugify_repo_name


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


def run_git_step(title: str, argv: list[str], auto: bool, verbose: bool) -> bool:
    print()
    print("=" * 72)
    print(title)
    print(f"  {format_git_argv(argv)}")
    log(verbose, f"[git-agent] cwd={Path.cwd()}")

    if not ask_yes_no("Run this command?", default="y", auto=auto):
        print("Stopped: this step was declined.")
        return False

    code, stdout, stderr = run_git(argv)
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    if code != 0:
        print(f"Error: command failed (exit code {code}).", file=sys.stderr)
        print(f"Suggested fix: {suggest_error_fix(stderr)}", file=sys.stderr)
        if not ask_yes_no("Continue with the remaining steps anyway?", default="n", auto=False):
            return False
    else:
        print("Success.")

    return True


def ensure_origin_remote(auto: bool, verbose: bool, private: bool) -> bool:
    if has_remote_origin():
        log(verbose, "[git-agent] origin remote already present.")
        print("\nUsing existing `origin` remote.")
        return True

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    default_name = slugify_repo_name(Path.cwd().name)

    if token:
        ok, login_msg = get_login(token)
        if not ok:
            print(
                f"GITHUB_TOKEN is set but GitHub API check failed: {login_msg}",
                file=sys.stderr,
            )
            print("Unset or fix the token, or add the remote manually when prompted.", file=sys.stderr)
            token = ""
        else:
            log(verbose, "[git-agent] GitHub token accepted by API.")

    repo_name = default_name
    if token:
        if not auto:
            entered = input(f"GitHub repository name [{default_name}]: ").strip()
            if entered:
                repo_name = slugify_repo_name(entered)

        kind = "private" if private else "public"
        if not ask_yes_no(
            f"Create a {kind} GitHub repository named '{repo_name}' and set it as origin?",
            default="y",
            auto=auto,
        ):
            token = ""

    if token:
        ok, msg, clone_url = create_user_repository(token, repo_name, private=private)
        if ok and clone_url:
            print(f"\nRepository ready: {msg}")
            if has_remote_origin():
                title = "Point origin to the new GitHub repository"
                argv = ["remote", "set-url", "origin", clone_url]
            else:
                title = "Add Git remote origin"
                argv = ["remote", "add", "origin", clone_url]
            if not run_git_step(title, argv, auto, verbose):
                return False
            if has_remote_origin():
                _, url, _ = run_git(["remote", "get-url", "origin"])
                if url:
                    log(verbose, f"[git-agent] origin -> {url}")
                return True
            print(
                "origin is still not configured. Paste a repository URL below.",
                file=sys.stderr,
            )
        else:
            print(f"GitHub API could not create the repository: {msg}", file=sys.stderr)
            print("You can paste a repository URL next.", file=sys.stderr)

    while True:
        url = input("\nPaste GitHub repository URL (HTTPS or SSH). Leave empty to cancel:\n> ").strip()
        if not url:
            print("Cancelled: no origin remote configured.", file=sys.stderr)
            return False

        if has_remote_origin():
            argv = ["remote", "set-url", "origin", url]
            label = "Update origin URL"
        else:
            argv = ["remote", "add", "origin", url]
            label = "Add origin remote"

        if not run_git_step(label, argv, auto, verbose):
            continue

        if has_remote_origin():
            return True

        print("origin is still missing. Try another URL.", file=sys.stderr)


def cmd_push(args: argparse.Namespace) -> int:
    auto = bool(args.yes)
    verbose = bool(args.verbose)
    private = bool(args.private)

    print("git-agent push")
    print("-" * 72)

    if not is_git_repo():
        if not run_git_step("Initialize Git repository", ["init"], auto, verbose):
            return 1
        if not is_git_repo():
            print("Still not a Git repository after git init.", file=sys.stderr)
            return 1

    if git_status_porcelain():
        if not run_git_step("Stage all changes", ["add", "."], auto, verbose):
            return 1

    need_commit = (not has_commits()) or bool(git_status_porcelain()) or has_staged_changes()
    if need_commit:
        if not has_commits() and not has_staged_changes() and not git_status_porcelain():
            commit_argv = ["commit", "--allow-empty", "-m", "Initial commit"]
        else:
            commit_argv = ["commit", "-m", "Initial commit"]
        if not run_git_step("Create commit", commit_argv, auto, verbose):
            return 1

    branch = get_current_branch()
    if branch != "main":
        if not run_git_step("Rename branch to main", ["branch", "-M", "main"], auto, verbose):
            return 1

    if not ensure_origin_remote(auto, verbose, private):
        return 1

    if not run_git_step("Push to GitHub", ["push", "-u", "origin", "main"], auto, verbose):
        return 1

    print()
    print("=" * 72)
    print("Done. Your project is pushed to GitHub (branch main, upstream set).")
    return 0


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

    push_p = sub.add_parser("push", help="Initialize, commit, set origin, and push to GitHub.")
    push_p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto mode: run all steps without confirmation prompts.",
    )
    push_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print extra diagnostics to stderr.",
    )
    push_p.add_argument(
        "--private",
        action="store_true",
        help="When creating a repo via GITHUB_TOKEN, make it private.",
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
