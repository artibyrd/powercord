# ruff: noqa: E402
import sys
from pathlib import Path

from fasthtml.common import Div

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from app.main_ui import extension_card  # noqa: E402
from app.ui.components import (
    Accordion,
    Card,
    DangerButton,
    FormInput,
    FormLabel,
    HealthScoreArc,
    PrimaryButton,
    SecondaryButton,
    TabGroup,
)  # noqa: E402

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


def test_health_score_arc():
    arc = HealthScoreArc(score=85, alert_count=5)
    assert arc.tag == "div"
    assert "flex" in arc.attrs["class"]
    svg_el = arc.children[0]
    assert svg_el.tag == "svg"
    assert any("text-success" in getattr(c, "attrs", {}).get("class", "") for c in svg_el.children)
    assert any("85%" in c.children for c in svg_el.children if getattr(c, "tag", None) == "text")
    assert any("5 alerts" in c.children for c in svg_el.children if getattr(c, "tag", None) == "text")


def test_tab_group():
    tabs = [("Active", "/url1", True), ("Inactive", "/url2", False)]
    tg = TabGroup(tabs, "target_div")
    assert tg.tag == "div"
    assert "tabs" in tg.attrs["class"]
    assert len(tg.children) == 2
    assert tg.children[0].tag == "a"
    assert "tab-active" in tg.children[0].attrs["class"]
    assert tg.children[0].attrs["hx-target"] == "#target_div"
    assert tg.children[0].attrs["hx-get"] == "/url1"
    assert "tab-active" not in tg.children[1].attrs["class"]
    assert tg.children[1].attrs["hx-target"] == "#target_div"
    assert tg.children[1].attrs["hx-get"] == "/url2"


def test_accordion():
    acc = Accordion("My Title", Div("Content"), open=True)
    assert acc.tag == "details"
    assert "collapse" in acc.attrs["class"]
    assert acc.attrs["open"] == "open"
    summary = acc.children[0]
    assert summary.tag == "summary"
    assert "My Title" in summary.children
    content_div = acc.children[1]
    assert content_div.tag == "div"
    assert "collapse-content" in content_div.attrs["class"]


def test_format_details():
    from app.extensions.utilities.widget import format_details

    # Test empty input
    assert format_details("") == ""
    assert format_details(None) == ""

    # Test 1: CategoryPermissionBaseline
    details1 = (
        "Target Role '@everyone' has less restricted overwrites. Leaked allows: 'Administrator', leaked denies: none."
    )
    res1 = format_details(details1)
    assert res1.tag == "div"
    html_str = str(res1)
    assert "Target Role" in html_str
    assert "@everyone" in html_str
    assert "has less restricted overwrites" in html_str
    assert "Administrator" in html_str
    assert "badge-error" in html_str  # leaked allows color
    assert "None" in html_str  # leaked denies none

    # Test 2: Other permissions markers
    details2 = "Role 'Staff' (position 10) has sensitive permissions: 'View Channel', 'Send Messages'."
    res2 = format_details(details2)
    assert res2.tag == "div"
    html_str = str(res2)
    assert "Role" in html_str
    assert "Staff" in html_str
    assert "position 10" in html_str
    assert "View Channel" in html_str
    assert "Send Messages" in html_str
    assert "badge-warning" in html_str

    # Test 3: Highlight quotes
    details3 = "Role 'Guest' below separator is mentionable."
    res3 = format_details(details3)
    assert res3.tag == "div"
    html_str = str(res3)
    assert "Guest" in html_str
    assert "text-accent font-bold" in html_str
