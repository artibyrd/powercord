# mypy: ignore-errors
"""FastHTML widget for configuring auditor settings (admin role, channels)."""

import json

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole
from app.ui.components import Card

engine = init_connection_engine()


def guild_admin_auditor_settings_widget(guild_id: int):
    """Renders the settings card for managing auditor configurations."""
    with Session(engine) as session:
        config = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).first()
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        roles = sorted(roles, key=lambda x: x.position, reverse=True)
        all_channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()

    # Reconstruct Discord-like channel hierarchy & order:
    categories = sorted([c for c in all_channels if c.type == "category"], key=lambda x: x.position)
    cat_ids = {cat.id for cat in categories}

    category_children = {}
    for c in all_channels:
        if c.type == "category":
            continue
        if c.parent_id is not None and c.parent_id in cat_ids:
            category_children.setdefault(c.parent_id, []).append(c)

    for cat_id in category_children:
        category_children[cat_id] = sorted(category_children[cat_id], key=lambda x: x.position)

    categoryless_channels = sorted(
        [c for c in all_channels if c.type != "category" and (c.parent_id is None or c.parent_id not in cat_ids)],
        key=lambda x: x.position,
    )

    ordered_channels = []
    for chan in categoryless_channels:
        ordered_channels.append((chan, False))

    for cat in categories:
        ordered_channels.append((cat, True))
        for child in category_children.get(cat.id, []):
            ordered_channels.append((child, False))

    selected_role_id = config.staff_separator_role_id if config else None

    staff_ids_set = set()
    ann_ids_set = set()
    if config:
        try:
            staff_ids_set = {int(x) for x in json.loads(config.staff_channel_ids or "[]") if x is not None}
        except Exception:  # noqa: S110
            pass
        try:
            ann_ids_set = {int(x) for x in json.loads(config.announcement_channel_ids or "[]") if x is not None}
        except Exception:  # noqa: S110
            pass

    role_options = [Option("Not configured — select a role...", value="", selected=(selected_role_id is None))]
    for role in roles:
        role_options.append(Option(role.name, value=str(role.id), selected=(role.id == selected_role_id)))

    # Pre-calculate category children IDs to check if all children are checked
    cat_children_ids = {}
    for cat in categories:
        cat_children_ids[cat.id] = [child.id for child in category_children.get(cat.id, [])]

    staff_checkboxes = []
    ann_checkboxes = []
    for chan, is_cat in ordered_channels:
        if is_cat:
            # Pre-select category if its ID is explicitly in the saved list,
            # or if it has children and all children are checked.
            children_ids = cat_children_ids.get(chan.id, [])
            staff_selected = (chan.id in staff_ids_set) or (
                len(children_ids) > 0 and all(cid in staff_ids_set for cid in children_ids)
            )
            ann_selected = (chan.id in ann_ids_set) or (
                len(children_ids) > 0 and all(cid in ann_ids_set for cid in children_ids)
            )

            staff_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="staff_channel_ids",
                        value=str(chan.id),
                        checked=staff_selected,
                        cls="checkbox checkbox-primary checkbox-xs category-checkbox",
                        data_category_id=str(chan.id),
                    ),
                    Span(f" 📁 {chan.name.upper()}", cls="label-text ml-2 font-bold"),
                    cls="flex items-center p-1 rounded hover:bg-base-300 cursor-pointer text-xs channel-item font-semibold opacity-90",
                    data_name=chan.name.lower(),
                )
            )

            ann_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="announcement_channel_ids",
                        value=str(chan.id),
                        checked=ann_selected,
                        cls="checkbox checkbox-primary checkbox-xs category-checkbox",
                        data_category_id=str(chan.id),
                    ),
                    Span(f" 📁 {chan.name.upper()}", cls="label-text ml-2 font-bold"),
                    cls="flex items-center p-1 rounded hover:bg-base-300 cursor-pointer text-xs channel-item font-semibold opacity-90",
                    data_name=chan.name.lower(),
                )
            )
        else:
            staff_selected = chan.id in staff_ids_set
            ann_selected = chan.id in ann_ids_set

            parent_attrs = {}
            indent_cls = ""
            if chan.parent_id is not None and chan.parent_id in cat_ids:
                parent_attrs["data_parent_id"] = str(chan.parent_id)
                indent_cls = " pl-6"

            staff_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="staff_channel_ids",
                        value=str(chan.id),
                        checked=staff_selected,
                        cls="checkbox checkbox-primary checkbox-xs",
                        **parent_attrs,
                    ),
                    Span(f" #{chan.name}", cls="label-text ml-2 font-medium"),
                    cls=f"flex items-center p-1{indent_cls} rounded hover:bg-base-300 cursor-pointer text-xs channel-item",
                    data_name=chan.name.lower(),
                )
            )

            ann_checkboxes.append(
                Label(
                    Input(
                        type="checkbox",
                        name="announcement_channel_ids",
                        value=str(chan.id),
                        checked=ann_selected,
                        cls="checkbox checkbox-primary checkbox-xs",
                        **parent_attrs,
                    ),
                    Span(f" #{chan.name}", cls="label-text ml-2 font-medium"),
                    cls=f"flex items-center p-1{indent_cls} rounded hover:bg-base-300 cursor-pointer text-xs channel-item",
                    data_name=chan.name.lower(),
                )
            )

    tabs_nav = Div(
        Button(
            "Admin Role",
            type="button",
            id="tab-btn-role",
            cls="tab tab-active transition-all duration-200 !bg-primary !text-primary-content font-extrabold shadow-md border border-primary/30",
            onclick="switchAuditorTab('role')",
        ),
        Button(
            "Staff Channels",
            type="button",
            id="tab-btn-staff",
            cls="tab transition-all duration-200 text-base-content/70",
            onclick="switchAuditorTab('staff')",
        ),
        Button(
            "Announcement Channels",
            type="button",
            id="tab-btn-ann",
            cls="tab transition-all duration-200 text-base-content/70",
            onclick="switchAuditorTab('ann')",
        ),
        cls="tabs tabs-boxed mb-4 grid grid-cols-3",
    )

    panel_role = Div(
        Div(
            Div(
                Label("Lowest Admin Role", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Select the lowest role in your hierarchy that is considered admin. This role and all roles above it are treated as admin. All roles below it are non-admin and subject to security auditing.",
                ),
                cls="flex items-center gap-2",
            ),
            Select(*role_options, name="staff_separator_role_id", cls="select select-bordered w-full"),
            cls="form-control mb-4",
        ),
        id="panel-role",
        cls="tab-panel mb-4",
    )

    panel_staff = Div(
        Div(
            Div(
                Label("Staff Channels", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Select Discord channels that are considered staff-only. The auditor checks whether non-staff roles can view these channels.",
                ),
                cls="flex items-center gap-2",
            ),
            Input(
                type="text",
                placeholder="Search staff channels...",
                cls="input input-bordered input-xs w-full mb-2",
                oninput="const q = this.value.toLowerCase(); document.getElementById('staff-channels-list').querySelectorAll('.channel-item').forEach(el => { el.style.display = el.getAttribute('data-name').includes(q) ? 'flex' : 'none'; })",
            ),
            Div(
                *staff_checkboxes,
                id="staff-channels-list",
                cls="flex-1 min-h-0 overflow-y-auto border border-base-300 rounded-md p-2 space-y-1 bg-base-200/50 channels-list",
            ),
            cls="form-control mb-4 h-full min-h-0 flex flex-col",
        ),
        id="panel-staff",
        cls="tab-panel hidden mb-4 h-full min-h-0 flex flex-col",
    )

    panel_ann = Div(
        Div(
            Div(
                Label("Announcement Channels", cls="label text-sm font-semibold"),
                Div(
                    I(cls="fa-solid fa-circle-info text-info opacity-60 cursor-help"),
                    cls="tooltip tooltip-right",
                    data_tip="Select Discord channels designated for announcements. The auditor checks whether non-staff roles can send messages or mention everyone in these channels.",
                ),
                cls="flex items-center gap-2",
            ),
            Input(
                type="text",
                placeholder="Search announcement channels...",
                cls="input input-bordered input-xs w-full mb-2",
                oninput="const q = this.value.toLowerCase(); document.getElementById('ann-channels-list').querySelectorAll('.channel-item').forEach(el => { el.style.display = el.getAttribute('data-name').includes(q) ? 'flex' : 'none'; })",
            ),
            Div(
                *ann_checkboxes,
                id="ann-channels-list",
                cls="flex-1 min-h-0 overflow-y-auto border border-base-300 rounded-md p-2 space-y-1 bg-base-200/50 channels-list",
            ),
            cls="form-control mb-4 h-full min-h-0 flex flex-col",
        ),
        id="panel-ann",
        cls="tab-panel hidden mb-4 h-full min-h-0 flex flex-col",
    )

    form_content = Form(
        tabs_nav,
        panel_role,
        panel_staff,
        panel_ann,
        Button("Save Settings", type="submit", cls="btn btn-primary w-full mt-auto"),
        Script("""
if (!window.auditorSettingsInitialized) {
    window.auditorSettingsInitialized = true;

    window.switchAuditorTab = function(tabName) {
        const panels = ['role', 'staff', 'ann'];
        panels.forEach(name => {
            const panel = document.getElementById('panel-' + name);
            if (panel) panel.classList.add('hidden');

            const btn = document.getElementById('tab-btn-' + name);
            if (btn) {
                btn.classList.remove('tab-active', '!bg-primary', '!text-primary-content', 'font-extrabold', 'shadow-md', 'border', 'border-primary/30');
                btn.classList.add('text-base-content/70');
            }
        });

        const activePanel = document.getElementById('panel-' + tabName);
        if (activePanel) activePanel.classList.remove('hidden');

        const activeBtn = document.getElementById('tab-btn-' + tabName);
        if (activeBtn) {
            activeBtn.classList.remove('text-base-content/70');
            activeBtn.classList.add('tab-active', '!bg-primary', '!text-primary-content', 'font-extrabold', 'shadow-md', 'border', 'border-primary/30');
        }

        localStorage.setItem('activeAuditorTab', tabName);
    };

    document.addEventListener('change', function(e) {
        if (!e.target) return;
        if (e.target.classList.contains('category-checkbox')) {
            const catId = e.target.getAttribute('data-category-id');
            const checked = e.target.checked;
            const container = e.target.closest('.channels-list');
            if (container) {
                container.querySelectorAll('input[data-parent-id="' + catId + '"]').forEach(el => {
                    el.checked = checked;
                });
            }
        } else if (e.target.hasAttribute('data-parent-id')) {
            const parentId = e.target.getAttribute('data-parent-id');
            const container = e.target.closest('.channels-list');
            if (container) {
                const catCheckbox = container.querySelector('input[data-category-id="' + parentId + '"]');
                if (catCheckbox) {
                    const siblings = container.querySelectorAll('input[data-parent-id="' + parentId + '"]');
                    const allChecked = Array.from(siblings).every(el => el.checked);
                    catCheckbox.checked = allChecked;
                }
            }
        }
    });
}

(function() {
    const savedTab = localStorage.getItem('activeAuditorTab') || 'role';
    window.switchAuditorTab(savedTab);
})();
        """),
        hx_post=f"/dashboard/{guild_id}/auditor-settings",
        hx_target=f"#guild-admin-auditor-settings-{guild_id}",
        cls="flex flex-col h-full min-h-0",
    )

    return Card(
        "Auditor Settings",
        form_content,
        id=f"guild-admin-auditor-settings-{guild_id}",
        cls="min-h-[480px] max-h-[800px] h-full",
    )
