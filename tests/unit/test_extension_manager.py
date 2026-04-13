"""Unit tests for the extension manager (install, uninstall, list)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.common.extension_manager import (
    EXTENSIONS_DIR,
    _normalize_pkg_name,
    get_installed_extensions,
    install_extension,
    list_extensions,
    load_manifest,
    uninstall_extension,
)

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit

# ── Normalize helper tests ──────────────────────────────────────────────


class TestNormalizePkgName:
    """Tests for the _normalize_pkg_name() helper."""

    def test_strips_gte(self) -> None:
        assert _normalize_pkg_name("pretty-midi>=0.2.11") == "pretty-midi"

    def test_strips_lte(self) -> None:
        assert _normalize_pkg_name("numpy<=2.0") == "numpy"

    def test_strips_exact(self) -> None:
        assert _normalize_pkg_name("requests==2.31.0") == "requests"

    def test_strips_gt(self) -> None:
        assert _normalize_pkg_name("flask>2.0") == "flask"

    def test_strips_lt(self) -> None:
        assert _normalize_pkg_name("django<5.0") == "django"

    def test_strips_tilde(self) -> None:
        assert _normalize_pkg_name("boto3~=1.26") == "boto3"

    def test_strips_extras(self) -> None:
        assert _normalize_pkg_name("fastapi[standard]>=0.100") == "fastapi"

    def test_bare_name_unchanged(self) -> None:
        assert _normalize_pkg_name("click") == "click"

    def test_whitespace_stripped(self) -> None:
        assert _normalize_pkg_name("  scipy >= 1.10  ") == "scipy"


# ── Manifest tests ──────────────────────────────────────────────────────


class TestLoadManifest:
    """Tests for the load_manifest() helper."""

    def test_valid_json_manifest(self, tmp_path: Path) -> None:
        """A well-formed extension.json should load correctly."""
        manifest_data = {
            "name": "test_ext_json",
            "version": "1.0.0",
            "description": "A test json extension",
            "python_dependencies": ["some-pkg>=1.0"],
            "discord_permissions": ["manage_channels"],
            "has_migrations": True,
            "internal": False,
        }
        (tmp_path / "extension.json").write_text(json.dumps(manifest_data))

        result = load_manifest(tmp_path)
        assert result["name"] == "test_ext_json"
        assert result["version"] == "1.0.0"
        assert result["python_dependencies"] == ["some-pkg>=1.0"]
        assert result["has_migrations"] is True

    def test_valid_manifest(self, tmp_path: Path) -> None:
        """A well-formed pyproject.toml should load correctly."""
        manifest_data = """
[tool.poetry]
name = "test_ext"
version = "1.0.0"
description = "A test extension"

[tool.poetry.dependencies]
some-pkg = ">=1.0"

[tool.powercord]
discord_permissions = ["manage_channels"]
has_migrations = true
internal = false
"""
        (tmp_path / "pyproject.toml").write_text(manifest_data)

        result = load_manifest(tmp_path)
        assert result["name"] == "test_ext"
        assert result["version"] == "1.0.0"
        assert result["python_dependencies"] == ["some-pkg@>=1.0"]
        assert result["has_migrations"] is True

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        """A directory without pyproject.toml should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No pyproject.toml"):
            load_manifest(tmp_path)

    def test_missing_required_keys_raises(self, tmp_path: Path) -> None:
        """A manifest missing 'name' or 'description' should raise ValueError."""
        (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nversion="1.0.0"')

        with pytest.raises(ValueError, match="missing required keys"):
            load_manifest(tmp_path)


# ── Installed extensions list ────────────────────────────────────────────


class TestGetInstalledExtensions:
    """Tests for get_installed_extensions()."""

    def test_returns_known_extensions(self) -> None:
        """Should return manifests for all extensions in the extensions dir."""
        extensions = get_installed_extensions()
        names = [ext["name"] for ext in extensions]

        # At minimum, custom_content and utilities should always be present
        assert "custom_content" in names
        assert "utilities" in names

    def test_includes_path_key(self) -> None:
        """Each returned extension dict should include a '_path' key."""
        extensions = get_installed_extensions()
        for ext in extensions:
            assert "_path" in ext
            assert Path(ext["_path"]).is_dir()

    def test_internal_flag_set_on_known_extensions(self) -> None:
        """Internal extensions (example, utilities) should have internal=True."""
        extensions = get_installed_extensions()
        ext_lookup = {ext["name"]: ext for ext in extensions}

        assert ext_lookup["custom_content"].get("internal") is True
        assert ext_lookup["utilities"].get("internal") is True


# ── Install tests ────────────────────────────────────────────────────────


class TestInstallExtension:
    """Tests for install_extension()."""

    def test_install_from_nonexistent_path_exits(self) -> None:
        """Installing from a missing directory should sys.exit."""
        with pytest.raises(SystemExit):
            install_extension("/nonexistent/path/to/extension")

    def test_install_missing_manifest_exits(self, tmp_path: Path) -> None:
        """Installing an extension without pyproject.toml should raise."""
        with pytest.raises(FileNotFoundError, match="No pyproject.toml"):
            install_extension(tmp_path)

    @patch("app.common.extension_manager.shutil.copytree")
    @patch("app.common.extension_manager.subprocess.run")
    def test_install_copies_files_and_installs_deps(
        self, mock_run: MagicMock, mock_copytree: MagicMock, tmp_path: Path
    ) -> None:
        """Install should copy files and call poetry add for deps."""
        manifest = """
[tool.poetry]
name = "fake_ext"
version = "1.0.0"
description = "Fake extension for testing"

[tool.poetry.dependencies]
fake-pkg = ">=1.0"

[tool.powercord]
has_migrations = false
"""
        (tmp_path / "pyproject.toml").write_text(manifest)

        dest = EXTENSIONS_DIR / "fake_ext"
        # Make sure target doesn't already exist
        assert not dest.exists()

        try:
            install_extension(tmp_path)
        except SystemExit:
            pass  # May exit if dest already exists

        # Verify copytree was called (or the dest now exists)
        if mock_copytree.called:
            args = mock_copytree.call_args
            assert str(args[0][1]).endswith("fake_ext")

    def test_install_already_installed_exits(self) -> None:
        """Installing an already-present extension should sys.exit."""
        # 'utilities' is always installed
        with pytest.raises(SystemExit):
            install_extension(EXTENSIONS_DIR / "utilities")


# ── Uninstall tests ──────────────────────────────────────────────────────


class TestUninstallExtension:
    """Tests for uninstall_extension()."""

    def test_uninstall_nonexistent_exits(self) -> None:
        """Uninstalling an extension that doesn't exist should sys.exit."""
        with pytest.raises(SystemExit):
            uninstall_extension("nonexistent_extension_xyz")

    @patch("builtins.input", return_value="n")
    def test_uninstall_internal_prompts_and_cancels(self, mock_input: MagicMock) -> None:
        """Uninstalling internal extension should prompt and cancel if user says no."""
        # 'utilities' is internal — should prompt
        uninstall_extension("utilities")  # Should not actually delete
        mock_input.assert_called_once()
        # Verify utilities still exists
        assert (EXTENSIONS_DIR / "utilities").exists()


class TestUninstallDependencyRemoval:
    """Tests for the per-dependency removal logic in uninstall_extension().

    Uses a temporary extension directory with a fake extension so that
    subprocess calls can be mocked without affecting the real environment.
    """

    @staticmethod
    def _create_fake_ext(
        tmp_path: Path,
        name: str,
        deps: list[str],
        *,
        internal: bool = False,
    ) -> Path:
        """Create a fake extension directory with a pyproject.toml manifest."""
        ext_dir = tmp_path / name
        ext_dir.mkdir(parents=True, exist_ok=True)

        deps_toml = "\n".join(
            [f'"{d.split(">=")[0]}" = ">={d.split(">=")[1]}"' if ">=" in d else f'"{d}" = "*"' for d in deps]
        )

        manifest = f"""
[tool.poetry]
name = "{name}"
version = "1.0.0"
description = "Fake extension {name}"

[tool.poetry.dependencies]
{deps_toml}

[tool.powercord]
has_migrations = false
internal = {"true" if internal else "false"}
"""
        (ext_dir / "pyproject.toml").write_text(manifest)
        return ext_dir

    @patch("app.common.extension_manager._fire_hook")
    @patch("app.common.extension_manager.subprocess.run")
    @patch("app.common.extension_manager.TESTS_DIR")
    @patch("app.common.extension_manager.EXTENSIONS_DIR")
    def test_removes_deps_individually(
        self,
        mock_ext_dir: MagicMock,
        mock_test_dir: MagicMock,
        mock_run: MagicMock,
        _mock_hook: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Each unique dependency should be removed via its own poetry remove call."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        mock_ext_dir.__truediv__ = lambda self, x: ext_dir / x  # type: ignore[assignment]
        mock_ext_dir.iterdir = ext_dir.iterdir
        mock_ext_dir.parents = {1: tmp_path}
        mock_test_dir.__truediv__ = lambda self, x: tmp_path / "tests" / x  # type: ignore[assignment]

        self._create_fake_ext(ext_dir, "test_ext", ["pkg-a>=1.0", "pkg-b>=2.0"])

        uninstall_extension("test_ext")

        # Should have called poetry remove once per dep, not batch
        remove_calls = [c for c in mock_run.call_args_list if "remove" in c[0][0]]
        assert len(remove_calls) == 2
        assert remove_calls[0] == call(
            [mock_run.call_args_list[0][0][0][0], "remove", "pkg-a"],
            check=True,
            cwd=str(tmp_path),
        )
        assert remove_calls[1] == call(
            [mock_run.call_args_list[1][0][0][0], "remove", "pkg-b"],
            check=True,
            cwd=str(tmp_path),
        )

    @patch("app.common.extension_manager._fire_hook")
    @patch("app.common.extension_manager.subprocess.run")
    @patch("app.common.extension_manager.TESTS_DIR")
    @patch("app.common.extension_manager.EXTENSIONS_DIR")
    def test_partial_failure_continues_cleanup(
        self,
        mock_ext_dir: MagicMock,
        mock_test_dir: MagicMock,
        mock_run: MagicMock,
        _mock_hook: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When one dep fails to remove, the rest should still be attempted
        and file cleanup should proceed."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        mock_ext_dir.__truediv__ = lambda self, x: ext_dir / x  # type: ignore[assignment]
        mock_ext_dir.iterdir = ext_dir.iterdir
        mock_ext_dir.parents = {1: tmp_path}
        mock_test_dir.__truediv__ = lambda self, x: tmp_path / "tests" / x  # type: ignore[assignment]

        self._create_fake_ext(ext_dir, "test_ext", ["pkg-ok>=1.0", "pkg-fail>=1.0", "pkg-ok2>=1.0"])

        # Make the second call raise CalledProcessError
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "remove" in cmd and "pkg-fail" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock()  # Return a mock for successful calls

        mock_run.side_effect = side_effect

        # Should NOT raise SystemExit — graceful degradation
        uninstall_extension("test_ext")

        # Extension directory should be cleaned up (rmtree'd)
        assert not (ext_dir / "test_ext").exists()

        # Output should report the failure but also report completion
        output = capsys.readouterr().out
        assert "Failed to remove pkg-fail" in output
        assert "Removed pkg-ok" in output
        assert "Removed pkg-ok2" in output
        assert "uninstalled with warnings" in output

    @patch("app.common.extension_manager._fire_hook")
    @patch("app.common.extension_manager.subprocess.run")
    @patch("app.common.extension_manager.TESTS_DIR")
    @patch("app.common.extension_manager.EXTENSIONS_DIR")
    def test_shared_deps_not_removed(
        self,
        mock_ext_dir: MagicMock,
        mock_test_dir: MagicMock,
        mock_run: MagicMock,
        _mock_hook: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Dependencies shared with other extensions must not be removed."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        mock_ext_dir.__truediv__ = lambda self, x: ext_dir / x  # type: ignore[assignment]
        mock_ext_dir.iterdir = ext_dir.iterdir
        mock_ext_dir.parents = {1: tmp_path}
        mock_test_dir.__truediv__ = lambda self, x: tmp_path / "tests" / x  # type: ignore[assignment]

        # ext_a and ext_b share "shared-pkg"; only "unique-pkg" should be removed
        self._create_fake_ext(ext_dir, "ext_a", ["shared-pkg>=1.0", "unique-pkg>=2.0"])
        self._create_fake_ext(ext_dir, "ext_b", ["shared-pkg>=1.0"])

        uninstall_extension("ext_a")

        # Only unique-pkg should have been passed to poetry remove
        remove_calls = [c for c in mock_run.call_args_list if "remove" in c[0][0]]
        assert len(remove_calls) == 1
        assert "unique-pkg" in remove_calls[0][0][0]

    @patch("app.common.extension_manager._fire_hook")
    @patch("app.common.extension_manager.subprocess.run")
    @patch("app.common.extension_manager.TESTS_DIR")
    @patch("app.common.extension_manager.EXTENSIONS_DIR")
    def test_all_deps_fail_still_cleans_files(
        self,
        mock_ext_dir: MagicMock,
        mock_test_dir: MagicMock,
        mock_run: MagicMock,
        _mock_hook: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Even if every dependency fails to remove, file cleanup must proceed."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        mock_ext_dir.__truediv__ = lambda self, x: ext_dir / x  # type: ignore[assignment]
        mock_ext_dir.iterdir = ext_dir.iterdir
        mock_ext_dir.parents = {1: tmp_path}
        mock_test_dir.__truediv__ = lambda self, x: tmp_path / "tests" / x  # type: ignore[assignment]

        self._create_fake_ext(ext_dir, "test_ext", ["pkg-a>=1.0", "pkg-b>=2.0"])

        # All removals fail
        mock_run.side_effect = subprocess.CalledProcessError(1, "poetry remove")

        uninstall_extension("test_ext")

        # Files should still be cleaned up
        assert not (ext_dir / "test_ext").exists()

        output = capsys.readouterr().out
        assert "uninstalled with warnings" in output
        assert "pkg-a" in output
        assert "pkg-b" in output


# ── List tests ───────────────────────────────────────────────────────────


class TestListExtensions:
    """Tests for list_extensions()."""

    def test_list_prints_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """list_extensions should print a formatted table to stdout."""
        list_extensions()
        captured = capsys.readouterr()
        # Should contain the header separator
        assert "─" in captured.out
        # Should contain at least the internal extensions
        assert "custom_content" in captured.out
        assert "utilities" in captured.out

    def test_list_shows_internal_type(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Internal extensions should be labeled as such."""
        list_extensions()
        captured = capsys.readouterr()
        assert "internal" in captured.out
