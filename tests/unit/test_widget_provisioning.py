from unittest.mock import patch

import pytest
from sqlmodel import select

from app.db.models import GuildExtensionSettings, WidgetSettings
from app.ui.helpers import update_guild_extension_setting

pytestmark = pytest.mark.unit


def test_widget_provisioning_enable(session):
    guild_id = 800001
    extension_name = "utilities"

    try:
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

        # The utilities extension has 8 default widgets declared in extension.json
        assert len(widgets) == 8

        # Verify a specific widget's details
        overview_widget = next(w for w in widgets if w.widget_name == "guild_admin_security_overview_widget")
        assert overview_widget.display_order == 1
        assert overview_widget.column_span == 4
        assert overview_widget.is_enabled is True

        # Alerts widget
        alerts_widget = next(w for w in widgets if w.widget_name == "guild_admin_alerts_widget")
        assert alerts_widget.display_order == 2
        assert alerts_widget.column_span == 8
        assert alerts_widget.is_enabled is True

        # Auditor settings widget
        auditor_settings_widget = next(w for w in widgets if w.widget_name == "guild_admin_auditor_settings_widget")
        assert auditor_settings_widget.display_order == 3
        assert auditor_settings_widget.column_span == 12
        assert auditor_settings_widget.is_enabled is True

        # Audit roles widget
        audit_roles_widget = next(w for w in widgets if w.widget_name == "guild_admin_audit_roles_widget")
        assert audit_roles_widget.display_order == 4
        assert audit_roles_widget.column_span == 6
        assert audit_roles_widget.is_enabled is True

        # Audit channels widget
        audit_channels_widget = next(w for w in widgets if w.widget_name == "guild_admin_audit_channels_widget")
        assert audit_channels_widget.display_order == 5
        assert audit_channels_widget.column_span == 6
        assert audit_channels_widget.is_enabled is True

        # Audit permissions widget
        audit_permissions_widget = next(w for w in widgets if w.widget_name == "guild_admin_audit_permissions_widget")
        assert audit_permissions_widget.display_order == 6
        assert audit_permissions_widget.column_span == 12
        assert audit_permissions_widget.is_enabled is True

        # Sidebar widget
        sidebar_widget = next(w for w in widgets if w.widget_name == "guild_admin_utilities_sidebar")
        assert sidebar_widget.display_order == 9
        assert sidebar_widget.column_span == 12
        assert sidebar_widget.position_config == "left"
        assert sidebar_widget.is_enabled is True

        # Help bubble widget
        help_bubble_widget = next(w for w in widgets if w.widget_name == "guild_admin_utilities_help_bubble")
        assert help_bubble_widget.display_order == 10
        assert help_bubble_widget.column_span == 12
        assert help_bubble_widget.position_config == "bottom-right"
        assert help_bubble_widget.is_enabled is True
    finally:
        from sqlalchemy import text

        session.execute(text("DELETE FROM guild_extension_settings WHERE guild_id = :gid"), {"gid": guild_id})
        session.execute(text("DELETE FROM widget_settings WHERE guild_id = :gid"), {"gid": guild_id})
        session.commit()


def test_widget_provisioning_no_overwrite(session):
    guild_id = 800002
    extension_name = "utilities"

    try:
        # Pre-populate an existing widget setting (e.g. disabled or different values)
        existing = WidgetSettings(
            guild_id=guild_id,
            extension_name=extension_name,
            widget_name="guild_admin_security_overview_widget",
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

        # Total should still be 8 (1 existing + 7 newly provisioned)
        assert len(widgets) == 8

        overview_widget = next(w for w in widgets if w.widget_name == "guild_admin_security_overview_widget")
        assert overview_widget.display_order == 10
        assert overview_widget.column_span == 6
        assert overview_widget.is_enabled is False
    finally:
        from sqlalchemy import text

        session.execute(text("DELETE FROM guild_extension_settings WHERE guild_id = :gid"), {"gid": guild_id})
        session.execute(text("DELETE FROM widget_settings WHERE guild_id = :gid"), {"gid": guild_id})
        session.commit()


def test_widget_provisioning_disable(session):
    guild_id = 800003
    extension_name = "utilities"

    try:
        # Pre-populate widget settings
        session.add(
            WidgetSettings(
                guild_id=guild_id,
                extension_name=extension_name,
                widget_name="guild_admin_security_overview_widget",
                is_enabled=True,
            )
        )
        session.add(
            WidgetSettings(
                guild_id=guild_id,
                extension_name=extension_name,
                widget_name="guild_admin_alerts_widget",
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
    finally:
        from sqlalchemy import text

        session.execute(text("DELETE FROM guild_extension_settings WHERE guild_id = :gid"), {"gid": guild_id})
        session.execute(text("DELETE FROM widget_settings WHERE guild_id = :gid"), {"gid": guild_id})
        session.commit()
