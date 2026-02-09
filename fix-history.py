#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def require_git() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("git not found on PATH. Install Git for Windows and try again.")


def get_current_git_user(repo: Path) -> tuple[str, str]:
    name = run_git(["config", "--get", "user.name"], repo)
    email = run_git(["config", "--get", "user.email"], repo)
    if not name or not email:
        raise RuntimeError(
            "Current git user.name and/or user.email are not set.\n"
            "Set them with:\n"
            "  git config user.name \"Your Name\"\n"
            "  git config user.email \"you@example.com\""
        )
    return name, email


def ensure_repo(repo: Path) -> None:
    try:
        _ = run_git(["rev-parse", "--show-toplevel"], repo)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("This folder is not a git repository.") from exc


def rewrite_history(repo: Path, name: str, email: str) -> None:
    # This rewrites ALL branches and tags.
    env_filter = (
        f'GIT_AUTHOR_NAME="{name}"; '
        f'GIT_AUTHOR_EMAIL="{email}"; '
        f'GIT_COMMITTER_NAME="{name}"; '
        f'GIT_COMMITTER_EMAIL="{email}"; '
        "export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL;"
    )

    # Avoid "Cannot create a new backup" prompts.
    # --tag-name-filter cat rewrites tags to point to rewritten commits.
    args = [
        "filter-branch",
        "--force",
        "--env-filter",
        env_filter,
        "--tag-name-filter",
        "cat",
        "--",
        "--all",
    ]

    subprocess.run(["git", *args], cwd=repo, check=True)


def main() -> int:
    require_git()
    repo = Path.cwd()
    ensure_repo(repo)

    toplevel = Path(run_git(["rev-parse", "--show-toplevel"], repo))
    name, email = get_current_git_user(toplevel)

    print("Repository:", toplevel)
    print("Rewriting all commits to:")
    print(f"  name : {name}")
    print(f"  email: {email}")
    print("")
    print("WARNING: This rewrites history (all commit hashes will change).")
    print("Make sure you have a backup, and coordinate with anyone else using the repo.")
    print("")

    rewrite_history(toplevel, name, email)

    print("Done.")
    print("")
    print("Next steps:")
    print("  - Verify: git shortlog -sne --all")
    print("  - If this repo is on a remote, you will need to force-push:")
    print("      git push --force --all")
    print("      git push --force --tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
