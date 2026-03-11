from typing import Optional

from sqlalchemy import BigInteger, Column, Text
from sqlmodel import Field, SQLModel


class GuildExtensionSettings(SQLModel, table=True):
    __tablename__ = "guild_extension_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger))
    extension_name: str = Field(max_length=255)
    gadget_type: str = Field(max_length=50)  # "cog", "sprocket", "widget"
    is_enabled: bool = Field(default=False)


class WidgetSettings(SQLModel, table=True):
    __tablename__ = "widget_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger))
    extension_name: str = Field(max_length=255)
    widget_name: str = Field(max_length=255)
    is_enabled: bool = Field(default=False)
    display_order: int = Field(default=99)
    column_span: int = Field(default=4)  # Width in 12-column grid (1-12)
    grid_x: int = Field(default=0)  # X position in grid (0-11)
    grid_y: int = Field(default=0)  # Y position in grid (row)


class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"

    user_id: int = Field(sa_column=Column(BigInteger, primary_key=True))
    comment: Optional[str] = Field(default=None, max_length=255)


class DiscordRole(SQLModel, table=True):
    __tablename__ = "discord_roles"

    id: int = Field(sa_column=Column(BigInteger, primary_key=True, autoincrement=False))
    guild_id: int = Field(sa_column=Column(BigInteger, index=True))
    name: str = Field(max_length=255)
    permissions: int = Field(sa_column=Column(BigInteger))  # Bitfield
    position: int = Field(default=0)
    color: int = Field(default=0)
    is_hoisted: bool = Field(default=False)
    is_managed: bool = Field(default=False)
    is_mentionable: bool = Field(default=False)


class DiscordChannel(SQLModel, table=True):
    __tablename__ = "discord_channels"

    id: int = Field(sa_column=Column(BigInteger, primary_key=True, autoincrement=False))
    guild_id: int = Field(sa_column=Column(BigInteger, index=True))
    parent_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    name: str = Field(max_length=255)
    type: str = Field(max_length=50)  # text, voice, category, etc.
    position: int = Field(default=0)
    overwrites: Optional[str] = Field(default="{}", description="JSON string of permission overwrites")


class DashboardAccessRole(SQLModel, table=True):
    __tablename__ = "dashboard_access_roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger, index=True))
    role_id: int = Field(sa_column=Column(BigInteger))


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, max_length=255, unique=True)
    name: str = Field(max_length=255, unique=True)
    is_active: bool = Field(default=True)
    scopes: str = Field(default="[]", description="JSON list of valid scopes")


class ApiAccessRole(SQLModel, table=True):
    __tablename__ = "api_access_roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger, index=True))
    role_id: int = Field(sa_column=Column(BigInteger))
    extension_name: str = Field(max_length=255)


# ── Custom Content sanitization constants (Fix #1) ────────────────────
# Only allow tags/attributes that Quill.js actually produces.
# This follows the principle of least privilege.
CUSTOM_CONTENT_ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "u",
    "s",
    "a",
    "blockquote",
    "pre",
    "code",
    "h1",
    "h2",
    "h3",
    "ol",
    "ul",
    "li",
    "span",
    "sub",
    "sup",
    "img",
    "video",
    "iframe",
}

CUSTOM_CONTENT_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "*": {"class", "style"},
    # Note: "rel" is intentionally omitted — nh3 auto-injects "noopener noreferrer"
    # on all links via its default link_rel setting. Including "rel" here would panic.
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height"},
    "video": {"src", "controls", "width", "height"},
    "iframe": {"src", "frameborder", "allowfullscreen", "width", "height"},
    "span": {"style"},
}

# Only allow safe URL schemes — blocks javascript: URIs (Fix #3 defense-in-depth).
CUSTOM_CONTENT_URL_SCHEMES = {"http", "https", "mailto"}


def _sanitize_content(raw_content: str) -> str:
    """Sanitize HTML content using nh3 with an explicit whitelist.

    This is the single source of truth for content sanitization across
    the entire custom_content extension.
    """
    import nh3

    return nh3.clean(
        raw_content,
        tags=CUSTOM_CONTENT_ALLOWED_TAGS,
        attributes=CUSTOM_CONTENT_ALLOWED_ATTRIBUTES,
        url_schemes=CUSTOM_CONTENT_URL_SCHEMES,
    )


class CustomContentItem(SQLModel, table=True):
    __tablename__ = "custom_content_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger, index=True))
    name: str = Field(max_length=100)  # Capped at 100 chars for safety
    content: str = Field(default="", sa_column=Column(Text))
    format: str = Field(default="html", max_length=50)  # html or markdown
    has_frame: bool = Field(default=True)

    # Fix #4: Model-layer sanitization — always clean content on assignment
    def set_content(self, raw_content: str) -> None:
        """Sanitize and store content. All write paths should use this method."""
        self.content = _sanitize_content(raw_content)
