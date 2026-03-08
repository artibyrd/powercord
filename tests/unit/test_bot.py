from unittest.mock import MagicMock, patch

import pytest

from app.main_bot import get_prefix

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


# Test get_prefix
def test_get_prefix_no_guild():
    bot = MagicMock()
    message = MagicMock()
    message.guild = None
    assert get_prefix(bot, message) == 0


def test_get_prefix_with_guild():
    bot = MagicMock()
    message = MagicMock()
    message.guild = "test_guild"
    message.content = "$test"

    # Mocking when_mentioned_or since it returns a callable
    with patch("nextcord.ext.commands.when_mentioned_or") as mock_when_mentioned_or:
        mock_callable = MagicMock()
        mock_when_mentioned_or.return_value = mock_callable

        get_prefix(bot, message)

        mock_when_mentioned_or.assert_called_with("$", "Powercord", "Powerbot")
        mock_callable.assert_called_with(bot, message)
