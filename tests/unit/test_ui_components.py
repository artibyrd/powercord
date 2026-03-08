import sys
from pathlib import Path

from fasthtml.common import Div

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from app.main_ui import extension_card  # noqa: E402
from app.ui.components import Card, DangerButton, FormInput, FormLabel, PrimaryButton, SecondaryButton  # noqa: E402

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


def test_card_component_string_title():
    """Verify that the Card component renders correctly when passed a plain string title."""
    card = Card("Test Title", Div("Content"))

    # FastHTML components are standardized subclasses of FT, check tag and primary class
    assert card.tag == "div"
    assert "card" in card.attrs["class"]

    # Check header structure (Card wraps titles in H3 inside a card-body Div)
    header_div = card.children[0]
    assert "card-body" in header_div.attrs["class"]
    assert header_div.children[0].tag == "h3"
    assert header_div.children[0].children[0] == "Test Title"


def test_card_component_custom_title():
    """Verify that the Card component can accept and render custom FastHTML components as a title."""
    custom_title = Div("Custom Title", cls="custom-class")
    card = Card(custom_title, Div("Content"))

    # The first child of the card-body should be our exact custom component
    header_div = card.children[0]
    assert header_div.children[0] == custom_title


def test_ui_wrappers():
    """Verify that all basic UI component wrappers correctly apply DaisyUI classes and pass through kwargs."""

    # Test SecondaryButton wrapper logic
    btn_sec = SecondaryButton("Cancel", id="btn1")
    assert btn_sec.tag == "button"
    assert "btn-secondary" in btn_sec.attrs["class"]
    assert btn_sec.attrs["id"] == "btn1"
    assert "Cancel" in btn_sec.children

    # Test PrimaryButton wrapper logic
    btn_prim = PrimaryButton("Submit")
    assert btn_prim.tag == "button"
    assert "btn-primary" in btn_prim.attrs["class"]

    # Test DangerButton wrapper logic
    btn_dan = DangerButton("Delete")
    assert btn_dan.tag == "button"
    assert "btn-error" in btn_dan.attrs["class"]

    # Test FormLabel component configuration
    lbl = FormLabel("Username", for_="user_input")
    assert lbl.tag == "label"
    assert "label" in lbl.attrs["class"]
    assert "Username" in lbl.children

    # Test FormInput component classes and kwargs passthrough
    inp = FormInput(name="username", id="user_input", cls="extra-class")
    assert inp.tag == "input"
    assert "input" in inp.attrs["class"]
    assert "input-bordered" in inp.attrs["class"]
    assert "w-full" in inp.attrs["class"]
    assert "extra-class" in inp.attrs["class"]
    assert inp.attrs["name"] == "username"
    assert inp.attrs["id"] == "user_input"


def test_extension_card():
    # Mock the enabled states
    enabled_cogs = ["test_ext"]
    enabled_sprockets = []
    enabled_widgets = []

    # extension_card(name, gadgets, enabled_cogs, enabled_sprockets, enabled_widgets)
    card = extension_card("test_ext", ["cog", "widget"], enabled_cogs, enabled_sprockets, enabled_widgets)

    # Verify card structure
    assert "card" in card.attrs["class"]

    def find_checkbox_input(component):
        if hasattr(component, "tag") and component.tag == "input" and component.attrs.get("type") == "checkbox":
            return component
        if hasattr(component, "children"):
            for child in component.children:
                found = find_checkbox_input(child)
                if found:
                    return found
        return None

    # Check if the single Unified Toggle is checked (enabled)
    toggle_checkbox = find_checkbox_input(card)
    assert toggle_checkbox is not None
    assert toggle_checkbox.attrs.get("checked") == "checked"
    assert toggle_checkbox.attrs["name"] == "enabled"
    assert toggle_checkbox.attrs["id"] == "all-test_ext-global"
    assert "toggle-primary" in toggle_checkbox.attrs["class"]
