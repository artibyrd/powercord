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
