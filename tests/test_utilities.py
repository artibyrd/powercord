import os

import nextcord
import pytest
from fastapi import HTTPException

from app.api.dependencies import verify_api_key
from app.api.responses import ErrorResponse, StandardResponse
from app.bot.embeds import EmbedFactory
from app.ui.components import Card, PrimaryButton

# All tests in this module are unit tests.
pytestmark = pytest.mark.unit


# API Tests
def test_standard_response():
    resp = StandardResponse(data={"id": 1}, message="Test")
    assert resp.data == {"id": 1}
    assert resp.message == "Test"
    assert resp.status == "success"


def test_error_response():
    resp = ErrorResponse(message="Fail")
    assert resp.message == "Fail"
    assert resp.status == "error"


@pytest.mark.asyncio
async def test_verify_api_key():
    os.environ["API_RELOAD_KEY"] = "test-key"

    # Valid key
    await verify_api_key(authorization="Bearer test-key")

    # Invalid key
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(authorization="Bearer wrong-key")
    assert exc.value.status_code == 403

    # Missing header
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(authorization=None)
    assert exc.value.status_code == 401


# Bot Tests
def test_embed_factory():
    embed = EmbedFactory.success(title="Test", description="Desc")
    assert embed.title == "Test"
    assert embed.description == "Desc"
    assert embed.color.value == nextcord.Color.green().value

    embed = EmbedFactory.error(title="Error", description="Desc")
    assert embed.color.value == nextcord.Color.red().value


# UI Tests (Basic instantiation check)
def test_ui_components():
    btn = PrimaryButton("Click Me")
    assert "btn-primary" in btn.attrs["class"]

    card = Card(title="Title", content="Content")
    assert "card" in card.attrs["class"]
