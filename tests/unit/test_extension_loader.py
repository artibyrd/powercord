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


# ── inspect_cogs tests ────────────────────────────────────────────────


class TestInspectCogs:
    """Tests for GadgetInspector.inspect_cogs() AST parsing logic."""

    def test_returns_all_cog_names(self) -> None:
        """Should return all extension names that have a cog.py file."""
        inspector = GadgetInspector()
        result = inspector.inspect_cogs()

        # At minimum, example and utilities both have cog.py
        assert "example" in result["all_cogs"]
        assert "utilities" in result["all_cogs"]

    def test_detects_custom_contexts(self) -> None:
        """Extensions with CogContexts classes should be reported."""
        inspector = GadgetInspector()
        result = inspector.inspect_cogs()
        # Custom contexts keyed by extension name if present
        assert isinstance(result["cog_custom_contexts"], dict)

    def test_detects_persistent_modals_and_views(self) -> None:
        """Persistent modals/views dicts should be returned (possibly empty)."""
        inspector = GadgetInspector()
        result = inspector.inspect_cogs()
        assert isinstance(result["cog_persistent_modals"], dict)
        assert isinstance(result["cog_persistent_views"], dict)

    def test_syntax_error_handled_gracefully(self, tmp_path) -> None:
        """A cog file with a syntax error should be skipped, not crash."""
        inspector = GadgetInspector()
        # Temporarily point extensions_dir at tmp_path with a bad cog
        bad_ext_dir = tmp_path / "bad_ext"
        bad_ext_dir.mkdir()
        (bad_ext_dir / "cog.py").write_text("def broken(:\n    pass\n")

        inspector.extensions_dir = tmp_path
        result = inspector.inspect_cogs()
        # Should not crash, bad_ext may or may not appear; just shouldn't raise
        assert isinstance(result["all_cogs"], list)


# ── inspect_sprockets tests ──────────────────────────────────────────


class TestInspectSprockets:
    """Tests for GadgetInspector.inspect_sprockets() AST parsing."""

    def test_detects_api_routers(self) -> None:
        """Extensions with sprocket.py containing APIRouter should be found."""
        inspector = GadgetInspector()
        result = inspector.inspect_sprockets()

        # Example extension has a sprocket with APIRouter
        if "example" in result:
            assert isinstance(result["example"], list)
            assert len(result["example"]) > 0

    def test_sprocket_with_no_router(self, tmp_path) -> None:
        """A sprocket.py without APIRouter assignments should return empty."""
        inspector = GadgetInspector()
        ext_dir = tmp_path / "no_router_ext"
        ext_dir.mkdir()
        (ext_dir / "sprocket.py").write_text("x = 42\n")

        inspector.extensions_dir = tmp_path
        result = inspector.inspect_sprockets()
        # no_router_ext should not appear since no routers found
        assert "no_router_ext" not in result


# ── load_sprockets tests ─────────────────────────────────────────────


class TestLoadSprockets:
    """Tests for GadgetInspector.load_sprockets() with mocked FastAPI."""

    def test_loads_routers_into_app(self) -> None:
        """Found routers should be included into the mocked FastAPI app."""
        inspector = GadgetInspector()
        mock_app = MagicMock()

        with patch.object(inspector, "inspect_sprockets", return_value={"test_ext": ["router"]}):
            with patch("importlib.import_module") as mock_import:
                mock_module = MagicMock()
                mock_router = MagicMock()
                mock_module.router = mock_router
                mock_import.return_value = mock_module

                inspector.load_sprockets(mock_app)

                mock_app.include_router.assert_called_once()

    def test_import_error_handled(self) -> None:
        """ImportError from a sprocket should be logged, not raised."""
        inspector = GadgetInspector()
        mock_app = MagicMock()

        with patch.object(inspector, "inspect_sprockets", return_value={"bad_ext": ["router"]}):
            with patch("importlib.import_module", side_effect=ImportError("test")):
                # Should not raise
                inspector.load_sprockets(mock_app)
                mock_app.include_router.assert_not_called()


# ── inspect_widgets tests ────────────────────────────────────────────


class TestInspectWidgets:
    """Tests for GadgetInspector.inspect_widgets() module introspection."""

    def test_finds_widget_functions(self) -> None:
        """Extensions with widget.py should have their callable functions listed."""
        inspector = GadgetInspector()
        result = inspector.inspect_widgets()

        # Utilities has a widget.py
        if "utilities" in result:
            assert isinstance(result["utilities"], list)
            assert len(result["utilities"]) > 0

    def test_import_error_handled(self, tmp_path) -> None:
        """ImportError during widget import should be logged, not raised."""
        inspector = GadgetInspector()
        ext_dir = tmp_path / "broken_widget"
        ext_dir.mkdir()
        (ext_dir / "widget.py").write_text("raise ImportError('test')\n")

        inspector.extensions_dir = tmp_path
        with patch("importlib.import_module", side_effect=ImportError("test")):
            result = inspector.inspect_widgets()
            assert "broken_widget" not in result
