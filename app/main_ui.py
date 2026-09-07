# mypy: ignore-errors
from __future__ import annotations

import os
from pathlib import Path

try:
    # When running as a script (e.g. python app/main_ui.py)
    import bootstrap
except ImportError:
    # When importing as a module (e.g. pytest)
    from app import bootstrap
bootstrap.setup_project_root()

import app

app.setup_logging("powercord")

from fasthtml.common import *
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

import app.common.gsm_loader as gsecrets
from app.common.extension_loader import GadgetInspector
from app.ui.auth import auth_before, auth_router
from app.ui.dashboard import dashboard_router
from app.ui.helpers import (
    get_admin_guilds,
    get_guild_cogs,
    get_guild_sprockets,
    get_guild_widgets,
    get_internal_api_client,
    get_widget_name,
    get_widget_settings,
    is_gadget_enabled,
    notify_api_of_config_change,
    update_guild_extension_setting,
)
from app.ui.routes.admin import (
    _render_admin_list,
    admin_home,
    admin_router,
    extension_card,
    require_admin,
)
from app.ui.routes.guild import guild_router
from app.ui.routes.public import public_home, public_router

gsecrets.load_env()

# Define a Beforeware to apply authentication to all necessary routes.
# We skip public-facing, dev login, static, and extension-declared public paths.
beforeware = Beforeware(
    auth_before,
    skip=[
        "/",
        "/login",
        "/logout",
        "/auth/discord/callback",
        "/dev/login",
        r"/static/.*",
        r"/favicon\.ico",
    ],
)

# Dynamically collect public-facing paths declared by installed extensions
_route_inspector = GadgetInspector()
beforeware.skip.extend(_route_inspector.collect_public_paths())

# UI Theme and Asset Headers
hdrs = (
    Link(rel="icon", href="/static/favicon.png", type="image/png"),
    # DaisyUI component CSS must load BEFORE the Tailwind CDN play script.
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css"),
    Script(src="https://cdn.tailwindcss.com"),
    # Tell Tailwind play CDN that DaisyUI is a plugin to preserve synthwave theme classes
    Script("""tailwind.config = { daisyui: { themes: ["synthwave"] } }"""),
    Link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css"),
    Link(
        rel="stylesheet",
        href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400..900&family=Share+Tech+Mono&display=swap",
    ),
    Link(rel="stylesheet", href="/static/theme.css?v=synthwave_v4"),
    Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
    Script(
        src="https://cdn.jsdelivr.net/combine/npm/tone@14.7.77,npm/@magenta/music@1.23.1/es6/core.js,npm/html-midi-player@1.5.0"
    ),
)

# FastHTML Application Assembler
app, rt = fast_app(
    secret_key=os.getenv("POWERCORD_SESSION_KEY"),
    before=beforeware,
    hdrs=hdrs,
    htmlkw={"data-theme": "synthwave"},
    pico=False,
)

static_dir = Path(__file__).parent / "static"
app.routes.insert(0, Mount("/static", StaticFiles(directory=static_dir), name="static"))
setup_toasts(app)

# Mount modular route blueprints
auth_router.to_app(app)
public_router.to_app(app)
admin_router.to_app(app)
guild_router.to_app(app)
dashboard_router.to_app(app)

# Auto-register dynamic routes from installed extensions
_route_inspector.load_routes(rt)

# Backward-compatibility re-exports for test suites and external packages
__all__ = [
    "app",
    "rt",
    "public_home",
    "admin_home",
    "extension_card",
    "require_admin",
    "_render_admin_list",
    "get_admin_guilds",
    "get_guild_cogs",
    "get_guild_sprockets",
    "get_guild_widgets",
    "get_internal_api_client",
    "get_widget_name",
    "get_widget_settings",
    "is_gadget_enabled",
    "notify_api_of_config_change",
    "update_guild_extension_setting",
    "GadgetInspector",
]

if __name__ == "__main__":
    serve(reload=False)
