#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
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


def require_tool(tool_name: str, install_hint: str) -> None:
    if shutil.which(tool_name) is None:
        raise RuntimeError(f"{tool_name} not found on PATH. {install_hint}")


def ensure_repo(repo: Path) -> Path:
    try:
        top_level = run_git(["rev-parse", "--show-toplevel"], repo)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("This folder is not a git repository.") from exc
    return Path(top_level)


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


def get_existing_identities(repo: Path) -> list[tuple[str, str]]:
    output = run_git(["shortlog", "-sne", "--all"], repo)
    identities: list[tuple[str, str]] = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            _, rest = line.split("\t", 1)
        except ValueError:
            continue

        if "<" not in rest or not rest.endswith(">"):
            continue

        name, email = rest.rsplit(" <", 1)
        identities.append((name.strip(), email[:-1].strip()))

    return identities


def build_mailmap(
    identities: list[tuple[str, str]],
    canonical_name: str,
    canonical_email: str,
) -> str:
    lines: list[str] = []

    for old_name, old_email in identities:
        if old_name == canonical_name and old_email == canonical_email:
            continue

        lines.append(
            f"{canonical_name} <{canonical_email}> "
            f"{old_name} <{old_email}>"
        )

    return "\n".join(lines) + ("\n" if lines else "")


def rewrite_history(repo: Path, name: str, email: str) -> None:
    identities = get_existing_identities(repo)
    mailmap_content = build_mailmap(identities, name, email)

    if not mailmap_content:
        print("No differing author identities found. Nothing to rewrite.")
        return

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".mailmap",
        delete=False,
    ) as tmp_file:
        tmp_file.write(mailmap_content)
        mailmap_path = Path(tmp_file.name)

    try:
        subprocess.run(
            ["git", "filter-repo", "--force", "--mailmap", str(mailmap_path)],
            cwd=repo,
            check=True,
        )
    finally:
        mailmap_path.unlink(missing_ok=True)


def main() -> int:
    try:
        require_tool(
            "git",
            "Install Git and try again.",
        )
        require_tool(
            "git-filter-repo",
            "Install it first, for example with: pip install git-filter-repo",
        )

        repo = Path.cwd()
        top_level = ensure_repo(repo)
        name, email = get_current_git_user(top_level)

        print(f"Repository: {top_level}")
        print("Rewriting all commits to:")
        print(f"  name : {name}")
        print(f"  email: {email}")
        print()
        print("WARNING: This rewrites history. All commit hashes will change.")
        print("Make sure you have a backup and coordinate with anyone else using the repo.")
        print()

        rewrite_history(top_level, name, email)

        print("Done.")
        print()
        print("Next steps:")
        print("  - Verify: git shortlog -sne --all")
        print("  - If this repo has a remote, you will need to force-push:")
        print("      git push --force --all")
        print("      git push --force --tags")
        return 0

    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
