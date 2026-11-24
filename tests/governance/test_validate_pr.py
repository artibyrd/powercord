"""Hermetic unit tests for scripts/validate_pr.py (PR version-bump & parity gate)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATE_PR_SCRIPT = REPO_ROOT / "scripts" / "validate_pr.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import validate_pr  # noqa: E402


def _write_repo(
    tmp_path: Path,
    *,
    version: str = "2.5.0",
    changelog_heading: str | None = "2.5.0",
    agent_plugin_version: str | None = None,
) -> tuple[Path, Path]:
    repo = tmp_path / "powercord"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        f'[tool.poetry]\nname = "powercord"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    if changelog_heading is not None:
        (repo / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## [{changelog_heading}] - 2026-11-24\n\n* Entry.\n",
            encoding="utf-8",
        )
    plugin_path = tmp_path / "powercord-agent" / "plugin.json"
    if agent_plugin_version is not None:
        plugin_path.parent.mkdir(parents=True)
        plugin_path.write_text(
            json.dumps({"name": "powercord-agent", "version": agent_plugin_version}),
            encoding="utf-8",
        )
    return repo, plugin_path


@pytest.mark.unit
def test_validate_pr_passes_on_valid_feature_branch(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.5.0", changelog_heading="2.5.0", agent_plugin_version="2.5.0")
    errors = validate_pr.validate_pr(
        repo,
        branch="feat/v2.5.0-agy-v234-overlays",
        pr_title="[v2.5.0] Antigravity v2.34 & Governance Modernization",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert errors == []


@pytest.mark.unit
def test_validate_pr_fails_on_pr_title_version_mismatch(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.5.0", changelog_heading="2.5.0")
    errors = validate_pr.validate_pr(
        repo,
        branch="feat/v2.5.0-something",
        pr_title="[v2.4.0] Stale title tag",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert any("PR title version tag [v2.4.0]" in e for e in errors)


@pytest.mark.unit
def test_validate_pr_fails_when_feature_branch_unbumped(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.4.0", changelog_heading="2.4.0")
    errors = validate_pr.validate_pr(
        repo,
        branch="feature/new-thing",
        pr_title="Add new thing",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert any("requires a SemVer bump" in e for e in errors)


@pytest.mark.unit
def test_validate_pr_handles_double_digit_minor_semver_comparison(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.10.0", changelog_heading="2.10.0")
    errors = validate_pr.validate_pr(
        repo,
        branch="release/v2.10.0",
        pr_title="[v2.10.0] Release",
        base_version="2.9.0",
        agent_plugin_json=plugin_path,
    )
    assert errors == []


@pytest.mark.unit
def test_validate_pr_fails_on_changelog_heading_drift(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.5.0", changelog_heading="2.4.0")
    errors = validate_pr.validate_pr(
        repo,
        branch="feat/v2.5.0-change",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert any("CHANGELOG.md heading [2.4.0]" in e for e in errors)


@pytest.mark.unit
def test_validate_pr_enforces_bump_on_fix_and_hotfix_branches(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.4.0", changelog_heading="2.4.0")
    for branch_name in ("fix/cache-race", "hotfix/prod-timeout"):
        errors = validate_pr.validate_pr(
            repo,
            branch=branch_name,
            base_version="2.4.0",
            agent_plugin_json=plugin_path,
        )
        assert any("requires a SemVer bump" in e for e in errors), f"Expected bump error for {branch_name}"


@pytest.mark.unit
def test_validate_pr_supports_prerelease_title_tags(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.5.0", changelog_heading="2.5.0")
    ok_errors = validate_pr.validate_pr(
        repo,
        branch="feat/v2.5.0-rc1",
        pr_title="[v2.5.0-rc1] Pre-release candidate",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert ok_errors == []

    bad_errors = validate_pr.validate_pr(
        repo,
        branch="feat/v2.5.0-rc1",
        pr_title="[v2.4.0-rc1] Stale pre-release tag",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert any("PR title version tag [v2.4.0-rc1]" in e for e in bad_errors)


@pytest.mark.unit
def test_validate_pr_allows_exempt_branches_without_bump(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.4.0", changelog_heading="2.4.0")
    for branch_name in ("chore/typo-fix", "docs/readme-update", "ci/cache-poetry"):
        errors = validate_pr.validate_pr(
            repo,
            branch=branch_name,
            pr_title="Routine maintenance",
            base_version="2.4.0",
            agent_plugin_json=plugin_path,
        )
        assert errors == [], f"Expected {branch_name} to be exempt from bump check"


@pytest.mark.unit
def test_validate_pr_fails_on_sibling_plugin_json_drift_and_invalid_semver(tmp_path: Path) -> None:
    repo, plugin_path = _write_repo(tmp_path, version="2.5.0", changelog_heading="2.5.0", agent_plugin_version="2.0.2")
    errors = validate_pr.validate_pr(
        repo,
        branch="feat/v2.5.0-modernization",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert any("plugin.json" in e and "drifts" in e for e in errors)

    plugin_path.write_text(json.dumps({"name": "powercord-agent", "version": "not-semver"}), encoding="utf-8")
    errors_invalid = validate_pr.validate_pr(
        repo,
        branch="feat/v2.5.0-modernization",
        base_version="2.4.0",
        agent_plugin_json=plugin_path,
    )
    assert any("plugin.json" in e for e in errors_invalid)


@pytest.mark.unit
def test_validate_pr_cli_help_and_exit_codes(tmp_path: Path) -> None:
    help_proc = subprocess.run(
        [sys.executable, str(VALIDATE_PR_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_proc.returncode == 0
    assert "Validate Powercord PR" in help_proc.stdout

    repo, plugin_path = _write_repo(tmp_path, version="2.5.0", changelog_heading="2.5.0")
    ok_proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_PR_SCRIPT),
            "--repo-root",
            str(repo),
            "--branch",
            "feat/v2.5.0-test",
            "--pr-title",
            "[v2.5.0] Test PR",
            "--base-version",
            "2.4.0",
            "--agent-plugin-json",
            str(plugin_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok_proc.returncode == 0
    assert "PASSED" in ok_proc.stdout

    fail_proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_PR_SCRIPT),
            "--repo-root",
            str(repo),
            "--branch",
            "feat/v2.5.0-test",
            "--pr-title",
            "[v2.9.9] Wrong tag",
            "--base-version",
            "2.4.0",
            "--agent-plugin-json",
            str(plugin_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert fail_proc.returncode == 1
    assert "FAILED" in fail_proc.stderr
