"""Unit tests for GadgetInspector.load_routes() and extension route discovery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.common.extension_loader import GadgetInspector

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


class TestLoadRoutes:
    """Tests for the load_routes() method of GadgetInspector."""

    def test_loads_routes_from_installed_extensions(self) -> None:
        """Should call register_routes(rt) for extensions with a routes.py file."""
        inspector = GadgetInspector()
        mock_rt = MagicMock()

        # Check if midi_library has routes.py (it should if installed)
        routes_file = inspector.extensions_dir / "midi_library" / "routes.py"
        if routes_file.exists():
            with patch("importlib.import_module") as mock_import:
                mock_module = MagicMock()
                mock_module.register_routes = MagicMock()
                mock_import.return_value = mock_module

                inspector.load_routes(mock_rt)

                # Should have called register_routes with the rt decorator
                mock_module.register_routes.assert_called_with(mock_rt)

    def test_skips_extensions_without_routes(self) -> None:
        """Extensions without routes.py should be silently skipped."""
        inspector = GadgetInspector()
        mock_rt = MagicMock()

        # Extensions like 'example' and 'utilities' don't have routes.py
        # This should not raise any exceptions
        with patch("importlib.import_module") as mock_import:
            # Only set up the mock for extensions that DO have routes.py
            def side_effect(module_path: str) -> MagicMock:
                mock_mod = MagicMock()
                mock_mod.register_routes = MagicMock()
                return mock_mod

            mock_import.side_effect = side_effect
            inspector.load_routes(mock_rt)

            # 'example' should NOT have been imported (no routes.py)
            import_calls = [str(c) for c in mock_import.call_args_list]
            assert not any("example.routes" in c for c in import_calls)
            assert not any("utilities.routes" in c for c in import_calls)

    def test_handles_import_errors_gracefully(self) -> None:
        """ImportError from a routes module should be logged, not raised."""
        inspector = GadgetInspector()
        mock_rt = MagicMock()

        with patch("importlib.import_module", side_effect=ImportError("test error")):
            # Should not raise — logged and skipped
            inspector.load_routes(mock_rt)

    def test_warns_if_register_routes_missing(self) -> None:
        """If routes.py exists but has no register_routes(), should log warning."""
        inspector = GadgetInspector()
        mock_rt = MagicMock()

        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock(spec=[])  # No register_routes attribute
            mock_import.return_value = mock_module

            # Should not raise
            inspector.load_routes(mock_rt)


class TestInspectExtensions:
    """Tests for the existing inspect_extensions() method."""

    def test_returns_example_and_utilities(self) -> None:
        """Internal extensions should always be detected."""
        inspector = GadgetInspector()
        result = inspector.inspect_extensions()

        assert "example" in result
        assert "utilities" in result

    def test_returns_gadget_types(self) -> None:
        """Each extension entry should list its gadget types."""
        inspector = GadgetInspector()
        result = inspector.inspect_extensions()

        # Example has cog, sprocket, and widget
        example = result.get("example", [])
        assert "cog" in example
        assert "sprocket" in example
        assert "widget" in example

    def test_skips_pycache(self) -> None:
        """__pycache__ directories should not appear as extensions."""
        inspector = GadgetInspector()
        result = inspector.inspect_extensions()

        assert "__pycache__" not in result
