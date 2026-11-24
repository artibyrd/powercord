#!/usr/bin/env python3
"""Shift-left PR version-bump, title, CHANGELOG, and plugin parity validator.

Pure Python standard library (zero third-party dependencies) so it executes reliably
in local hooks, Justfile recipes (`just pr-create`), and minimal GitHub Actions runners.

Policy scope:
- Version progression and CHANGELOG heading parity are enforced on `feat/`, `feature/`,
  `fix/`, `hotfix/`, and `release/` branches (`docs/`, `ci/`, and `chore/` are exempt).
- PR title tags support `[vMAJOR.MINOR.PATCH]` and optional pre-release suffixes
  such as `[vMAJOR.MINOR.PATCH-rc1]`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")
PR_TITLE_VERSION_RE = re.compile(r"\[v(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\]")
CHANGELOG_HEADING_RE = re.compile(r"^##\s+\[(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\]", re.MULTILINE)
VERSION_BUMP_BRANCH_PREFIXES = ("feat/", "feature/", "fix/", "hotfix/", "release/")


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a MAJOR.MINOR.PATCH[-prerelease] SemVer string into its core (M, m, p) tuple."""
    match = SEMVER_RE.match(version.strip())
    if not match:
        raise ValueError(f"Invalid SemVer string: {version!r} (expected MAJOR.MINOR.PATCH[-prerelease])")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _semver_sort_key(version: str) -> tuple[int, int, int, int, str]:
    """Return a SemVer comparison key where final releases sort above pre-releases of the same core version."""
    match = SEMVER_RE.match(version.strip())
    if not match:
        raise ValueError(f"Invalid SemVer string: {version!r} (expected MAJOR.MINOR.PATCH[-prerelease])")
    prerelease = match.group(4)
    is_final = 1 if prerelease is None else 0
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), is_final, prerelease or "")


def read_pyproject_version(pyproject_path: Path) -> str:
    """Read package version from [tool.poetry] or [project] in pyproject.toml."""
    if not pyproject_path.is_file():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    poetry_ver = data.get("tool", {}).get("poetry", {}).get("version")
    if isinstance(poetry_ver, str) and poetry_ver.strip():
        return poetry_ver.strip()
    project_ver = data.get("project", {}).get("version")
    if isinstance(project_ver, str) and project_ver.strip():
        return project_ver.strip()
    raise ValueError(f"No version field found in {pyproject_path}")


def read_latest_changelog_version(changelog_path: Path) -> str | None:
    """Return the first ## [X.Y.Z] version heading from CHANGELOG.md, or None if absent."""
    if not changelog_path.is_file():
        return None
    content = changelog_path.read_text(encoding="utf-8")
    match = CHANGELOG_HEADING_RE.search(content)
    return match.group(1) if match else None


def extract_pr_title_version(pr_title: str) -> str | None:
    """Extract the X.Y.Z[-prerelease] version from a [vX.Y.Z(-...)] tag in a PR title, if present."""
    match = PR_TITLE_VERSION_RE.search(pr_title)
    return match.group(1) if match else None


def _title_version_matches(title_version: str, current_version: str) -> bool:
    """Return True if a PR title version tag matches pyproject.toml version (allowing pre-release title for release)."""
    if title_version == current_version:
        return True
    # Allow e.g. [v2.5.0-rc1] targeting pyproject.toml version 2.5.0, while rejecting mismatched cores or rc tags.
    if "-" in title_version and "-" not in current_version:
        return title_version.split("-", 1)[0] == current_version
    return False


def is_version_bump_branch(branch: str) -> bool:
    """Return True when the branch prefix requires a SemVer version bump over base."""
    normalized = branch.strip()
    return any(normalized.startswith(prefix) for prefix in VERSION_BUMP_BRANCH_PREFIXES)


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    git_bin = shutil.which("git")
    if not git_bin:
        return None
    return subprocess.run(  # noqa: S603
        [git_bin, "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def detect_current_branch(repo_root: Path) -> str:
    """Detect the currently checked-out git branch name."""
    proc = _run_git(repo_root, ["symbolic-ref", "--short", "HEAD"])
    if proc and proc.returncode == 0:
        return proc.stdout.strip()
    return ""


def read_base_pyproject_version(repo_root: Path, base_ref: str) -> str | None:
    """Read pyproject.toml version from a git ref (e.g. origin/main or main)."""
    for ref in (base_ref, "main") if base_ref != "main" else (base_ref,):
        proc = _run_git(repo_root, ["show", f"{ref}:pyproject.toml"])
        if proc and proc.returncode == 0 and proc.stdout:
            data = tomllib.loads(proc.stdout)
            poetry_ver = data.get("tool", {}).get("poetry", {}).get("version")
            if isinstance(poetry_ver, str) and poetry_ver.strip():
                return poetry_ver.strip()
            project_ver = data.get("project", {}).get("version")
            if isinstance(project_ver, str) and project_ver.strip():
                return project_ver.strip()
    return None


def validate_pr(
    repo_root: Path,
    *,
    branch: str | None = None,
    pr_title: str | None = None,
    base_ref: str = "origin/main",
    base_version: str | None = None,
    agent_plugin_json: Path | None = None,
) -> list[str]:
    """Validate PR metadata, SemVer progression, CHANGELOG parity, and optional plugin.json parity.

    Returns a list of error strings (empty list means all checks passed).
    """
    errors: list[str] = []
    pyproject_path = repo_root / "pyproject.toml"
    changelog_path = repo_root / "CHANGELOG.md"

    try:
        current_version = read_pyproject_version(pyproject_path)
        current_tuple = parse_semver(current_version)
        current_key = _semver_sort_key(current_version)
    except (FileNotFoundError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"pyproject.toml version check failed: {exc}"]

    # 1. PR title [vX.Y.Z(-...)] parity check (when tag is present in title)
    if pr_title:
        title_version = extract_pr_title_version(pr_title)
        if title_version and not _title_version_matches(title_version, current_version):
            errors.append(
                f"PR title version tag [v{title_version}] does not match pyproject.toml version {current_version}."
            )

    resolved_branch = branch if branch is not None else detect_current_branch(repo_root)

    # 2 & 3. Feature/fix/hotfix/release branch version progression + CHANGELOG heading parity
    if is_version_bump_branch(resolved_branch):
        resolved_base = base_version if base_version is not None else read_base_pyproject_version(repo_root, base_ref)
        if resolved_base is None:
            errors.append(
                f"Could not read base version from '{base_ref}:pyproject.toml' to verify version bump on branch '{resolved_branch}'."
            )
        else:
            try:
                base_key = _semver_sort_key(resolved_base)
                if current_key <= base_key:
                    errors.append(
                        f"Branch '{resolved_branch}' requires a SemVer bump in pyproject.toml: "
                        f"current={current_version} is not greater than {base_ref}={resolved_base}."
                    )
            except ValueError as exc:
                errors.append(f"Invalid base SemVer ({resolved_base}): {exc}")

        if changelog_path.is_file():
            latest_changelog = read_latest_changelog_version(changelog_path)
            if latest_changelog != current_version:
                errors.append(
                    f"Latest CHANGELOG.md heading [{latest_changelog or 'NONE'}] does not match "
                    f"pyproject.toml version [{current_version}]."
                )

    # 4. Optional sibling powercord-agent/plugin.json SemVer & major.minor parity
    plugin_path = (
        agent_plugin_json if agent_plugin_json is not None else repo_root.parent / "powercord-agent" / "plugin.json"
    )
    if plugin_path.is_file():
        try:
            plugin_data = json.loads(plugin_path.read_text(encoding="utf-8"))
            plugin_version = str(plugin_data.get("version", "")).strip()
            plugin_tuple = parse_semver(plugin_version)
            if plugin_tuple[:2] != current_tuple[:2]:
                errors.append(
                    f"Sibling {plugin_path.name} version ({plugin_version}) major.minor drifts from "
                    f"powercord pyproject.toml ({current_version})."
                )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"Sibling powercord-agent/plugin.json validation failed: {exc}")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Powercord PR version-bump parity, CHANGELOG heading, and optional plugin.json SemVer."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to the powercord repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Current branch name (default: auto-detected from git HEAD).",
    )
    parser.add_argument(
        "--pr-title",
        default=None,
        help="Pull request title to check for [vX.Y.Z(-...)] parity.",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git base ref used to read baseline pyproject.toml version (default: origin/main).",
    )
    parser.add_argument(
        "--base-version",
        default=None,
        help="Explicit baseline SemVer string (overrides --base-ref lookup, useful for CI/tests).",
    )
    parser.add_argument(
        "--agent-plugin-json",
        type=Path,
        default=None,
        help="Optional path to sibling powercord-agent/plugin.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    errors = validate_pr(
        repo_root=args.repo_root.resolve(),
        branch=args.branch,
        pr_title=args.pr_title,
        base_ref=args.base_ref,
        base_version=args.base_version,
        agent_plugin_json=args.agent_plugin_json,
    )
    if errors:
        print("PR validation FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    version = read_pyproject_version(args.repo_root.resolve() / "pyproject.toml")
    print(f"PR validation PASSED (version {version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
