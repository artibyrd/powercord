import pytest
from sqlmodel import Session

from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole
from app.extensions.utilities.widget import guild_admin_auditor_settings_widget

pytestmark = pytest.mark.unit

def test_auditor_settings_channel_ordering_and_categories(session: Session):
    guild_id = 777888

    # 1. Setup config, roles, and channels in database
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_channel_ids="[101, 102]",  # child channels checked, category 100 should be auto-checked on render
        announcement_channel_ids="[200]"  # category 200 explicitly checked, category checkbox should be checked
    )

    role = DiscordRole(id=1, guild_id=guild_id, name="Admin", permissions=8, position=1)

    # Categories
    cat_staff = DiscordChannel(id=100, guild_id=guild_id, parent_id=None, name="Staff Category", type="category", position=1)
    cat_ann = DiscordChannel(id=200, guild_id=guild_id, parent_id=None, name="Announcements Category", type="category", position=2)

    # Uncategorized channels
    chan_uncat_2 = DiscordChannel(id=302, guild_id=guild_id, parent_id=None, name="general-2", type="text", position=1)
    chan_uncat_1 = DiscordChannel(id=301, guild_id=guild_id, parent_id=None, name="general-1", type="text", position=0)

    # Child channels under Staff
    chan_staff_2 = DiscordChannel(id=102, guild_id=guild_id, parent_id=100, name="staff-chat-2", type="text", position=1)
    chan_staff_1 = DiscordChannel(id=101, guild_id=guild_id, parent_id=100, name="staff-chat-1", type="text", position=0)

    # Child channels under Ann
    chan_ann_1 = DiscordChannel(id=201, guild_id=guild_id, parent_id=200, name="ann-1", type="text", position=0)

    session.add_all([
        config, role, cat_staff, cat_ann,
        chan_uncat_2, chan_uncat_1,
        chan_staff_2, chan_staff_1, chan_ann_1
    ])
    session.commit()

    # 2. Render the widget
    from fasthtml.common import to_xml
    widget = guild_admin_auditor_settings_widget(guild_id)
    html = to_xml(widget)

    # 3. Assertions

    # Verify categories are present and uppercase with folder icon
    assert "📁 STAFF CATEGORY" in html
    assert "📁 ANNOUNCEMENTS CATEGORY" in html

    # Verify channels are present
    assert "#general-1" in html
    assert "#general-2" in html
    assert "#staff-chat-1" in html
    assert "#staff-chat-2" in html
    assert "#ann-1" in html

    # Verify category checkboxes have the proper category attributes and classes
    assert 'class="checkbox checkbox-primary checkbox-xs category-checkbox"' in html
    assert 'data-category-id="100"' in html
    assert 'data-category-id="200"' in html

    # Verify child channels have parent data attributes
    assert 'data-parent-id="100"' in html
    assert 'data-parent-id="200"' in html

    # Verify child channel indent class is present
    assert 'pl-6' in html

    # Verify JavaScript event listener check is embedded
    assert "window.auditorSettingsInitialized" in html
    assert "data-category-id" in html
    assert "data-parent-id" in html
