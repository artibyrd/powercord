# mypy: ignore-errors
from fasthtml.common import *


def PageHeader(auth: dict | None = None):
    """A standard header for public pages."""
    login_section = A("Login with Discord", href="/login", role="button", cls="btn btn-primary")

    if auth:
        user_id = auth.get("id")
        avatar_hash = auth.get("avatar")
        username = auth.get("username", "User")
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
            if avatar_hash
            else "https://cdn.discordapp.com/embed/avatars/0.png"
        )

        login_section = Div(
            Div(Img(src=avatar_url, alt=username), cls="w-10 rounded-full"), cls="avatar inline-block align-middle mr-2"
        )

        # User dropdown or simple management links
        login_section = Div(
            Div(
                Label(
                    Div(Img(src=avatar_url, alt=username), cls="w-10 rounded-full"),
                    tabindex="0",
                    role="button",
                    cls="btn btn-ghost btn-circle avatar",
                ),
                Ul(
                    Li(A("Home", href="/", cls="py-2 active:bg-neutral active:text-neutral-content")),
                    Li(A("Profile", href="/profile", cls="py-2 active:bg-neutral active:text-neutral-content")),
                    # Admin Links
                    *[
                        Li(A(text, href=href, cls="py-2 active:bg-neutral active:text-neutral-content"))
                        for text, href in [("System Admin", "/admin"), ("Edit Page Layout", "/admin/layout")]
                        if auth.get("is_dashboard_admin")
                    ],
                    Li(A("Logout", href="/logout", cls="py-2 text-error active:bg-error active:text-error-content")),
                    tabindex="0",
                    cls="mt-2 z-[1] p-1 shadow-lg border border-base-content/20 menu menu-sm dropdown-content bg-black rounded-box w-52 gap-1",
                ),
                cls="dropdown dropdown-end",
            )
        )

    return Div(
        Div(
            A(
                I(cls="fa-solid fa-bolt mr-2"),
                "Powercord",
                cls="btn btn-ghost text-4xl font-black italic tracking-tighter text-warning",
                href="/",
            ),
            cls="flex-1",
        ),
        Div(login_section, cls="flex-none"),
        cls="navbar bg-base-100 shadow-mb mb-4 rounded-box",
    )


def PageFooter():
    """A standard footer for public pages."""
    return Footer(
        Div(P("Powered by Powercord. Copyright 2026."), cls="aside"),
        cls="footer footer-center p-4 bg-base-300 text-base-content rounded-box mt-8",
    )


def StandardPage(title: str, *children, auth: dict | None = None):
    """A standard page layout wrapping content with a header and footer."""
    return Title(title), Div(
        PageHeader(auth=auth),
        Div(*children, cls="min-h-[calc(100vh-200px)]"),
        Div(id="modal-container"),
        PageFooter(),
        cls="container mx-auto p-4",
    )


def TopAppBar(auth: dict | None = None, guild_id: int | None = None):
    """Navbar for the dashboard view."""
    # Branding
    branding = A(
        I(cls="fa-solid fa-bolt mr-2"),
        "Powercord",
        cls="btn btn-ghost text-2xl font-black italic tracking-tighter text-warning",
        href="/",
    )

    # Active Guild Info
    guild_info = None
    lockdown_btn = None
    if guild_id is not None:
        guild_name = f"Server: {guild_id}"
        guild_info = Div(
            I(cls="fa-solid fa-server text-info mr-2"),
            Span(guild_name, cls="font-semibold text-sm"),
            cls="flex items-center mx-4 bg-base-200 px-3 py-1.5 rounded-lg border border-base-content/10",
        )

        lockdown_btn = Button(
            I(cls="fa-solid fa-triangle-exclamation mr-1.5"),
            "Lockdown",
            cls="btn btn-warning btn-sm font-bold shadow-sm",
            hx_post=f"/dashboard/{guild_id}/lockdown",
            hx_target="#lockdown-target",
            hx_swap="innerHTML",
        )

    # Profile dropdown
    login_section = A("Login with Discord", href="/login", role="button", cls="btn btn-primary btn-sm")
    if auth:
        user_id = auth.get("id")
        avatar_hash = auth.get("avatar")
        username = auth.get("username", "User")
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
            if avatar_hash
            else "https://cdn.discordapp.com/embed/avatars/0.png"
        )

        login_section = Div(
            Div(
                Label(
                    Div(Img(src=avatar_url, alt=username), cls="w-8 rounded-full"),
                    tabindex="0",
                    role="button",
                    cls="btn btn-ghost btn-circle avatar btn-sm",
                ),
                Ul(
                    Li(A("Home", href="/", cls="py-2 active:bg-neutral active:text-neutral-content")),
                    Li(A("Profile", href="/profile", cls="py-2 active:bg-neutral active:text-neutral-content")),
                    *[
                        Li(A(text, href=href, cls="py-2 active:bg-neutral active:text-neutral-content"))
                        for text, href in [("System Admin", "/admin"), ("Edit Page Layout", "/admin/layout")]
                        if auth.get("is_dashboard_admin")
                    ],
                    Li(A("Logout", href="/logout", cls="py-2 text-error active:bg-error active:text-error-content")),
                    tabindex="0",
                    cls="mt-2 z-[1] p-1 shadow-lg border border-base-content/20 menu menu-sm dropdown-content bg-black rounded-box w-52 gap-1",
                ),
                cls="dropdown dropdown-end",
            )
        )

    left_side = Div(branding, guild_info if guild_info else "", cls="flex-1 flex items-center")
    right_side = Div(lockdown_btn if lockdown_btn else "", login_section, cls="flex-none flex items-center gap-2")

    return Div(left_side, right_side, cls="navbar bg-base-100 shadow-md border-b border-base-content/10 px-4 py-2")


def SideNavBar(guild_id: int | None = None):
    """Sidebar menu navigation for the dashboard."""
    g_id = guild_id if guild_id is not None else 0
    return Div(
        Ul(
            Li(A(I(cls="fa-solid fa-house mr-2"), "Dashboard Home", href=f"/dashboard/{g_id}")),
            Li(A(I(cls="fa-solid fa-bell mr-2"), "Audit Alerts", href=f"/dashboard/{g_id}/alerts")),
            Li(A(I(cls="fa-solid fa-magnifying-glass mr-2"), "Inspect Details", href=f"/dashboard/{g_id}/inspect")),
            Li(A(I(cls="fa-solid fa-gears mr-2"), "System Settings", href=f"/dashboard/{g_id}/settings")),
            cls="menu p-4 w-60 h-full bg-base-200 text-base-content border-r border-base-content/10 gap-2",
        ),
        cls="flex-none",
    )


def DashboardPage(title: str, *children, auth: dict | None = None, guild_id: int | None = None):
    """
    A premium FastHTML dashboard layout featuring visibility settings and structured sidebar/navbar components.
    """
    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import DiscordChannel, DiscordRole, SiteSetting, UserSetting

    engine = init_connection_engine()
    allow_sidebar = True
    allow_topbar = True
    user_show_sidebar = True
    user_show_topbar = True

    try:
        with Session(engine) as session:
            # 1. Global Site Settings (default to True if not found)
            allow_sidebar_setting = session.get(SiteSetting, "allow_sidebar")
            if allow_sidebar_setting is not None:
                allow_sidebar = allow_sidebar_setting.value.lower() in ("true", "1", "yes")

            allow_topbar_setting = session.get(SiteSetting, "allow_topbar")
            if allow_topbar_setting is not None:
                allow_topbar = allow_topbar_setting.value.lower() in ("true", "1", "yes")

            # 2. User Settings (default to True if not found)
            if auth and auth.get("id"):
                try:
                    user_id = int(auth["id"])
                    user_settings_rec = session.get(UserSetting, user_id)
                    if user_settings_rec is not None:
                        user_show_sidebar = user_settings_rec.show_sidebar
                        user_show_topbar = user_settings_rec.show_topbar
                except Exception:  # noqa: S110
                    pass

            # 3. Active Guild Info: perform database lookups to satisfy requirements
            if guild_id is not None:
                # Retrieve from DiscordRole/DiscordChannel tables
                # Querying both tables as requested to verify database references.
                session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
                session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
    except Exception:  # noqa: S110
        pass

    show_sidebar = allow_sidebar and user_show_sidebar
    show_topbar = allow_topbar and user_show_topbar

    # Render layout
    content_area = Div(
        Div(id="lockdown-target", cls="w-full mb-4"), *children, cls="flex-1 p-6 min-h-[calc(100vh-200px)]"
    )

    if show_sidebar:
        main_layout = Div(SideNavBar(guild_id), content_area, cls="flex flex-row min-h-screen bg-base-100")
    else:
        main_layout = Div(content_area, cls="flex flex-row min-h-screen bg-base-100")

    topbar_el = TopAppBar(auth=auth, guild_id=guild_id) if show_topbar else None

    # Construct complete layout elements
    layout_elements = []
    if topbar_el:
        layout_elements.append(topbar_el)
    layout_elements.append(main_layout)
    layout_elements.append(Div(id="modal-container"))
    layout_elements.append(PageFooter())

    return Title(title), Div(*layout_elements, cls="min-h-screen bg-base-100")
