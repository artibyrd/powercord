import os
import sys
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.getcwd())

from fasthtml.common import to_xml

from app.main_ui import extension_card


def test_api_link_present():
    print("Testing API link presence when sprocket is enabled...")

    # Mock the helper functions
    with (
        patch("app.ui.dashboard.get_guild_cogs", return_value=[]),
        patch("app.ui.dashboard.get_guild_sprockets", return_value=["example"]),
        patch("app.ui.dashboard.get_guild_widgets", return_value=[]),
    ):
        # Call the function
        # extension_name='example', gadgets=['sprocket'], guild_id=123
        card = extension_card("example", ["sprocket"], [], ["example"], [])

        # Convert to string/xml to check content
        card_html = to_xml(card)

        expected_url = "http://localhost:8000/docs#/example"

        if expected_url in card_html:
            print(f"SUCCESS: Link to {expected_url} found in card.")
        else:
            print(f"FAILURE: Link to {expected_url} NOT found in card.")
            print("Card HTML content:")
            print(card_html)
            sys.exit(1)


def test_api_link_absent():
    print("\nTesting API link absence when sprocket is disabled...")

    # Mock the helper functions - return empty list for sprockets
    with (
        patch("app.ui.dashboard.get_guild_cogs", return_value=[]),
        patch("app.ui.dashboard.get_guild_sprockets", return_value=[]),
        patch("app.ui.dashboard.get_guild_widgets", return_value=[]),
    ):
        # Call the function
        card = extension_card("example", ["sprocket"], [], [], [])

        # Convert to string/xml to check content
        card_html = to_xml(card)

        expected_url = "http://localhost:8000/docs#/example"

        if expected_url not in card_html:
            print(f"SUCCESS: Link to {expected_url} correctly absent.")
        else:
            print(f"FAILURE: Link to {expected_url} found but should be absent.")
            sys.exit(1)


if __name__ == "__main__":
    try:
        test_api_link_present()
        test_api_link_absent()
        print("\nAll verification tests passed!")
    except Exception as e:
        print(f"\nAn error occurred during verification: {e}")
        sys.exit(1)
