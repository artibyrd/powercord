from unittest.mock import patch

import pytest
from sqlmodel import select

from app.db.models import GuildExtensionSettings, WidgetSettings
from app.ui.helpers import update_guild_extension_setting

pytestmark = pytest.mark.unit


def test_widget_provisioning_enable(session):
    guild_id = 800001
    extension_name = "utilities"

    # Patch init_connection_engine to use our test database session's connection
    with patch("app.ui.helpers.init_connection_engine", return_value=session.get_bind()):
        # Enable the widget setting
        update_guild_extension_setting(
            guild_id=guild_id,
            extension_name=extension_name,
            gadget_type="widget",
            is_enabled=True,
        )

    # Verify GuildExtensionSettings is set
    ges = session.exec(
        select(GuildExtensionSettings).where(
            GuildExtensionSettings.guild_id == guild_id,
            GuildExtensionSettings.extension_name == extension_name,
            GuildExtensionSettings.gadget_type == "widget",
        )
    ).first()
    assert ges is not None
    assert ges.is_enabled is True

    # Verify that default widgets from extension.json were provisioned
    widgets = session.exec(
        select(WidgetSettings).where(
            WidgetSettings.guild_id == guild_id,
            WidgetSettings.extension_name == extension_name,
        )
    ).all()

    # The utilities extension has 6 default widgets declared in extension.json
    assert len(widgets) == 6

    # Verify a specific widget's details
    overview_widget = next(w for w in widgets if w.widget_name == "guild_admin_security_overview")
    assert overview_widget.display_order == 1
    assert overview_widget.column_span == 4
    assert overview_widget.is_enabled is True

    alerts_widget = next(w for w in widgets if w.widget_name == "guild_admin_alerts")
    assert alerts_widget.display_order == 2
    assert alerts_widget.column_span == 8
    assert alerts_widget.is_enabled is True


def test_widget_provisioning_no_overwrite(session):
    guild_id = 800002
    extension_name = "utilities"

    # Pre-populate an existing widget setting (e.g. disabled or different values)
    existing = WidgetSettings(
        guild_id=guild_id,
        extension_name=extension_name,
        widget_name="guild_admin_security_overview",
        is_enabled=False,
        display_order=10,
        column_span=6,
    )
    session.add(existing)
    session.commit()

    with patch("app.ui.helpers.init_connection_engine", return_value=session.get_bind()):
        update_guild_extension_setting(
            guild_id=guild_id,
            extension_name=extension_name,
            gadget_type="widget",
            is_enabled=True,
        )

    # Verify that the existing widget setting was NOT overwritten
    session.expire_all()
    widgets = session.exec(
        select(WidgetSettings).where(
            WidgetSettings.guild_id == guild_id,
            WidgetSettings.extension_name == extension_name,
        )
    ).all()

    # Total should still be 6 (1 existing + 5 newly provisioned)
    assert len(widgets) == 6

    overview_widget = next(w for w in widgets if w.widget_name == "guild_admin_security_overview")
    assert overview_widget.display_order == 10
    assert overview_widget.column_span == 6
    assert overview_widget.is_enabled is False


def test_widget_provisioning_disable(session):
    guild_id = 800003
    extension_name = "utilities"

    # Pre-populate widget settings
    session.add(
        WidgetSettings(
            guild_id=guild_id,
            extension_name=extension_name,
            widget_name="guild_admin_security_overview",
            is_enabled=True,
        )
    )
    session.add(
        WidgetSettings(
            guild_id=guild_id,
            extension_name=extension_name,
            widget_name="guild_admin_alerts",
            is_enabled=True,
        )
    )
    session.commit()

    with patch("app.ui.helpers.init_connection_engine", return_value=session.get_bind()):
        update_guild_extension_setting(
            guild_id=guild_id,
            extension_name=extension_name,
            gadget_type="widget",
            is_enabled=False,
        )

    # Verify that all widget settings for this extension and guild are deleted
    session.expire_all()
    widgets = session.exec(
        select(WidgetSettings).where(
            WidgetSettings.guild_id == guild_id,
            WidgetSettings.extension_name == extension_name,
        )
    ).all()
    assert len(widgets) == 0
