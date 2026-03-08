from typing import Optional

from sqlalchemy import BigInteger, Column
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
