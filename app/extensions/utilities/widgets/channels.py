# mypy: ignore-errors
"""FastHTML widget for inspecting guild channels, categories, and permission overwrites."""

import json
import logging

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.common.discord_constants import ALL_PERMISSIONS
from app.db.models import DiscordChannel
from app.ui.components import Accordion

engine = init_connection_engine()


def _get_common_legend(for_roles=False):
    items = []
    if for_roles:
        items.append(
            Li(
                Span("✅: ", cls="font-bold"),
                "Indicates if a role is Sidebar (displayed separately) or Bot/Int (managed by an integration).",
            )
        )
    else:
        items.append(
            Li(
                Span("Badges: ", cls="font-bold"),
                Span("Green", cls="badge badge-success badge-sm px-2 rounded-md mr-1"),
                "= Explicit Allow, ",
                Span("Red", cls="badge badge-error badge-sm px-2 rounded-md mr-1"),
                "= Explicit Deny.",
            )
        )
        items.append(Li(Span("Icons: ", cls="font-bold"), "📢=Text, 🔊=Voice, 🏛️=Forum, 📁=Category"))

    items.append(
        Li(
            Span("Note: ", cls="font-bold"),
            "Permissions shown are explicit overrides. Inherited permissions are not listed.",
        )
    )

    return Div(
        H4("Legend:", cls="font-bold text-sm mb-2 opacity-70"),
        Ul(*items, cls="list-disc list-inside text-xs opacity-70"),
        cls="bg-base-200/50 p-3 rounded-md mb-4",
    )


def guild_admin_audit_channels_widget(guild_id: int):
    """Displays Discord server channels for a specific guild.

    Groups channels by their parent category and visually indicates inherited
    versus explicit permission overwrites using FastHTML components.
    """
    import app.extensions.utilities.widget as w

    session_cls = getattr(w, "Session", Session)
    current_engine = getattr(w, "engine", engine)
    with session_cls(current_engine) as session:
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()

    if not channels:
        return Accordion(
            "Guild Channels",
            Div("No channels found for this server.", cls="opacity-70 text-sm mt-2"),
            open=False,
            id=f"guild-admin-audit-channels-{guild_id}",
        )

    channels = sorted(channels, key=lambda x: x.position)

    # Group by Category
    categories = {c.id: c for c in channels if c.type == "category"}
    uncategorized = []
    nested: dict[int, list[DiscordChannel]] = {}
    for c in channels:
        if c.type == "category":
            continue
        if c.parent_id:
            if c.parent_id not in nested:
                nested[c.parent_id] = []
            nested[c.parent_id].append(c)
        else:
            uncategorized.append(c)

    channel_rows = []

    def _build_overwrites_ui(overwrites_str, guild_id):
        is_private = False
        overwrites_ui = Span("-", cls="opacity-30 text-xs")
        detailed_perms_by_target = {}

        try:
            if overwrites_str:
                ov = json.loads(overwrites_str)
                if ov and len(ov) > 0:
                    ov_badges = []
                    # Check if @everyone is denied View Channel (1 << 10)
                    everyone_ov = ov.get(str(guild_id))
                    if everyone_ov and (everyone_ov.get("deny", 0) & (1 << 10)):
                        is_private = True

                    for target_id, access in ov.items():
                        name = access.get("name", target_id)
                        allow_val = access.get("allow", 0)
                        deny_val = access.get("deny", 0)

                        allow_count = allow_val.bit_count() if hasattr(int, "bit_count") else bin(allow_val).count("1")
                        deny_count = deny_val.bit_count() if hasattr(int, "bit_count") else bin(deny_val).count("1")

                        desc = []
                        if allow_count:
                            desc.append(f"{allow_count} Allowed")
                        if deny_count:
                            desc.append(f"{deny_count} Denied")
                        title_text = ", ".join(desc) if desc else "No Overrides"

                        color_cls = "badge-ghost"
                        if allow_count > 0 and deny_count == 0:
                            color_cls = "badge-success"
                        elif deny_count > 0 and allow_count == 0:
                            color_cls = "badge-error"
                        elif allow_count > 0 and deny_count > 0:
                            color_cls = "badge-warning"

                        # Build specific permissions UI for this target
                        target_detailed_perms = []
                        for perm_name, perm_value in ALL_PERMISSIONS.items():
                            if allow_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-success/20 text-success border border-success/30 w-full",
                                    )
                                )
                            elif deny_val & perm_value:
                                target_detailed_perms.append(
                                    Span(
                                        perm_name,
                                        cls="inline-flex justify-center items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-error/20 text-error border border-error/30 w-full",
                                    )
                                )

                        if target_detailed_perms:
                            detailed_perms_by_target[name] = Div(
                                *target_detailed_perms, cls="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2 mt-1"
                            )

                        ov_badges.append(
                            Span(
                                name,
                                cls=f"badge badge-sm px-2 rounded-md {color_cls} mr-1 mb-1 opacity-90",
                                title=title_text,
                            )
                        )
                    overwrites_ui = Div(*ov_badges, cls="flex flex-wrap")
        except Exception:
            logging.warning("Failed to parse channel overwrites", exc_info=True)
        return is_private, overwrites_ui, detailed_perms_by_target

    def channel_row(chan, indent=0, is_synced=False):
        icon = "📢"
        if "voice" in str(chan.type):
            icon = "🔊"
        elif "text" in str(chan.type):
            icon = "💬"
        elif "stage" in str(chan.type):
            icon = "🎭"
        elif "forum" in str(chan.type):
            icon = "🏛️"

        if is_synced:
            is_private, _, detailed_perms = _build_overwrites_ui(chan.overwrites, guild_id)
            overwrites_ui = Span(
                "Synced",
                cls="badge badge-sm badge-ghost opacity-50 rounded-md",
                title="Has identical explicit overwrites to its parent category.",
            )
        else:
            is_private, overwrites_ui, detailed_perms = _build_overwrites_ui(chan.overwrites, guild_id)

        if is_private:
            icon = f"🔒 {icon}"
            name_cls = "font-bold text-error"
        else:
            name_cls = "opacity-70"

        # Expandable Detail Content
        if not is_synced and detailed_perms:
            perms_sections = []
            for target_name, perms_div in detailed_perms.items():
                perms_sections.append(
                    Div(H5(target_name, cls="text-xs font-bold opacity-80 mb-1"), perms_div, cls="mb-3 last:mb-0")
                )
            detail_panel = Div(*perms_sections, cls="px-4 pb-4 pt-1 bg-base-300/20")

            summary_ui = Summary(
                Div(
                    Div(
                        Span(
                            "▶", cls="text-[8px] opacity-40 mr-2 group-open:rotate-90 transition-transform inline-block"
                        ),
                        icon,
                        Span(chan.name, cls=f"ml-2 {name_cls}"),
                        cls="col-span-5 flex items-center",
                        style=f"padding-left: {indent}em",
                    ),
                    Div(str(chan.id), cls="col-span-3 opacity-70 font-mono text-xs"),
                    Div(overwrites_ui, cls="col-span-4"),
                    cls="grid grid-cols-12 w-full items-center gap-2",
                ),
                cls="px-4 py-2 hover:bg-base-200/50 transition-colors cursor-pointer list-none",
            )
            return Details(summary_ui, detail_panel, cls="group border-b border-white/5")

        # Static Row without children/expander
        return Div(
            Div(
                Span(cls="w-4 inline-block mr-2"),  # Placeholder for arrow to align columns
                icon,
                Span(chan.name, cls=f"ml-2 {name_cls}"),
                cls="col-span-5 flex items-center",
                style=f"padding-left: {indent}em",
            ),
            Div(str(chan.id), cls="col-span-3 opacity-70 font-mono text-xs"),
            Div(overwrites_ui, cls="col-span-4"),
            cls="grid grid-cols-12 gap-2 px-4 py-2 border-b border-white/5 hover:bg-base-200/30 items-center",
        )

    # 1. Uncategorized Channels
    for c in uncategorized:
        channel_rows.append(channel_row(c, indent=0))

    # 2. Categorized Channels
    for cat_id, cat in categories.items():
        is_private, overwrites_ui, detailed_perms = _build_overwrites_ui(cat.overwrites, guild_id)
        icon = "🔒 📁" if is_private else "📁"
        name_cls = "font-bold text-error" if is_private else "font-bold uppercase tracking-wider text-xs opacity-90"

        summary_div = Div(
            Div(
                Span("▶", cls="text-[8px] opacity-40 mr-2 group-open:rotate-90 transition-transform inline-block"),
                icon,
                Span(cat.name.upper(), cls=f"ml-2 {name_cls}"),
                cls="col-span-5 flex items-center",
            ),
            Div(str(cat.id), cls="col-span-3 opacity-70 font-mono text-xs"),
            Div(overwrites_ui, cls="col-span-4"),
            cls="grid grid-cols-12 w-full items-center gap-2",
        )

        children = nested.get(cat_id, [])
        child_rows = []
        for child in children:
            is_synced = child.overwrites == cat.overwrites
            child_rows.append(channel_row(child, indent=1.5, is_synced=is_synced))

        # Include Category's own detailed permissions if any
        cat_detail_panel = []
        if detailed_perms:
            perms_sections = []
            for target_name, perms_div in detailed_perms.items():
                perms_sections.append(
                    Div(
                        H5(f"Category: {target_name}", cls="text-xs font-bold text-accent mb-1"),
                        perms_div,
                        cls="mb-3 last:mb-0",
                    )
                )
            cat_detail_panel.append(Div(*perms_sections, cls="px-4 pb-3 pt-1 bg-base-300/40 border-b border-white/5"))

        category_content = Div(*cat_detail_panel, *child_rows)

        channel_rows.append(
            Details(
                Summary(
                    summary_div,
                    cls="px-4 py-2 hover:bg-base-200/70 transition-colors cursor-pointer list-none bg-base-200/30",
                ),
                category_content,
                open=True,
                cls="group border-b border-white/10",
            )
        )

    guild_section = Div(
        # Header Row
        Div(
            Div("Name", cls="col-span-5 font-bold"),
            Div("ID", cls="col-span-3 font-bold"),
            Div("Explicit Overwrites", cls="col-span-4 font-bold"),
            cls="grid grid-cols-12 gap-2 px-4 py-2 text-xs uppercase opacity-70 border-b border-white/10 bg-base-300/30",
        ),
        Div(*channel_rows, cls="text-sm"),
        cls="w-full flex flex-col border border-white/10 rounded-lg overflow-hidden",
    )

    return Accordion(
        "Guild Channels",
        Div(_get_common_legend(for_roles=False), guild_section),
        open=False,
        id=f"guild-admin-audit-channels-{guild_id}",
    )
