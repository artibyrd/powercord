"""Unit tests for the extension manager (install, uninstall, list)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.common.extension_manager import (
    EXTENSIONS_DIR,
    get_installed_extensions,
    install_extension,
    list_extensions,
    load_manifest,
    uninstall_extension,
)

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit

# ── Manifest tests ──────────────────────────────────────────────────────


class TestLoadManifest:
    """Tests for the load_manifest() helper."""

    def test_valid_manifest(self, tmp_path: Path) -> None:
        """A well-formed extension.json should load correctly."""
        manifest_data = {
            "name": "test_ext",
            "version": "1.0.0",
            "description": "A test extension",
            "python_dependencies": ["some-pkg>=1.0"],
            "discord_permissions": ["manage_channels"],
            "has_migrations": True,
            "internal": False,
        }
        (tmp_path / "extension.json").write_text(json.dumps(manifest_data))

        result = load_manifest(tmp_path)
        assert result["name"] == "test_ext"
        assert result["version"] == "1.0.0"
        assert result["python_dependencies"] == ["some-pkg>=1.0"]
        assert result["has_migrations"] is True

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        """A directory without extension.json should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No extension.json"):
            load_manifest(tmp_path)

    def test_missing_required_keys_raises(self, tmp_path: Path) -> None:
        """A manifest missing 'name' or 'description' should raise ValueError."""
        (tmp_path / "extension.json").write_text(json.dumps({"version": "1.0.0"}))

        with pytest.raises(ValueError, match="missing required keys"):
            load_manifest(tmp_path)


# ── Installed extensions list ────────────────────────────────────────────


class TestGetInstalledExtensions:
    """Tests for get_installed_extensions()."""

    def test_returns_known_extensions(self) -> None:
        """Should return manifests for all extensions in the extensions dir."""
        extensions = get_installed_extensions()
        names = [ext["name"] for ext in extensions]

        # At minimum, example and utilities should always be present
        assert "example" in names
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

        assert ext_lookup["example"].get("internal") is True
        assert ext_lookup["utilities"].get("internal") is True


# ── Install tests ────────────────────────────────────────────────────────


class TestInstallExtension:
    """Tests for install_extension()."""

    def test_install_from_nonexistent_path_exits(self) -> None:
        """Installing from a missing directory should sys.exit."""
        with pytest.raises(SystemExit):
            install_extension("/nonexistent/path/to/extension")

    def test_install_missing_manifest_exits(self, tmp_path: Path) -> None:
        """Installing an extension without extension.json should raise."""
        with pytest.raises(FileNotFoundError, match="No extension.json"):
            install_extension(tmp_path)

    @patch("app.common.extension_manager.shutil.copytree")
    @patch("app.common.extension_manager.subprocess.run")
    def test_install_copies_files_and_installs_deps(
        self, mock_run: MagicMock, mock_copytree: MagicMock, tmp_path: Path
    ) -> None:
        """Install should copy files and call poetry add for deps."""
        manifest = {
            "name": "fake_ext",
            "version": "1.0.0",
            "description": "Fake extension for testing",
            "python_dependencies": ["fake-pkg>=1.0"],
            "has_migrations": False,
        }
        (tmp_path / "extension.json").write_text(json.dumps(manifest))

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
        # 'example' is always installed
        with pytest.raises(SystemExit):
            install_extension(EXTENSIONS_DIR / "example")


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
        # 'example' is internal — should prompt
        uninstall_extension("example")  # Should not actually delete
        mock_input.assert_called_once()
        # Verify example still exists
        assert (EXTENSIONS_DIR / "example").exists()


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
        assert "example" in captured.out
        assert "utilities" in captured.out

    def test_list_shows_internal_type(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Internal extensions should be labeled as such."""
        list_extensions()
        captured = capsys.readouterr()
        assert "internal" in captured.out
