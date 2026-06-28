import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, Text, func
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
    position_config: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


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
    key_hash: str = Field(index=True, max_length=255, unique=True)
    name: str = Field(max_length=255, unique=True)
    is_active: bool = Field(default=True)
    scopes: str = Field(default="[]", description="JSON list of valid scopes")
    key_type: str = Field(default="user", max_length=50)
    guild_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True, index=True))
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )


class ApiUserRole(SQLModel, table=True):
    __tablename__ = "api_user_roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger, unique=True, index=True))
    role_id: int = Field(sa_column=Column(BigInteger))


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


class DiscordAuditorConfig(SQLModel, table=True):
    __tablename__ = "discord_auditor_configs"

    guild_id: int = Field(sa_column=Column(BigInteger, primary_key=True, autoincrement=False))
    staff_separator_role_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    staff_channel_ids: str = Field(default="[]")
    announcement_channel_ids: str = Field(default="[]")


class SiteSetting(SQLModel, table=True):
    __tablename__ = "site_settings"

    key: str = Field(primary_key=True)
    value: str


class UserSetting(SQLModel, table=True):
    __tablename__ = "user_settings"

    user_id: int = Field(sa_column=Column(BigInteger, primary_key=True, autoincrement=False))
    show_topbar: bool = Field(default=True)


class SecurityAlertOverride(SQLModel, table=True):
    __tablename__ = "security_alert_overrides"

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger, index=True))
    alert_hash: str = Field(index=True)
    rule: str
    category: str
    message: str
    details: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    comment: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
