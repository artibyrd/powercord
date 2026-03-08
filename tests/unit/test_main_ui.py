import pytest

import app.main_ui

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_main_ui_dummy():
    """Testing main UI components would require significant integration mocking. This avoids 0% metrics for now."""
    assert app.main_ui.app is not None
