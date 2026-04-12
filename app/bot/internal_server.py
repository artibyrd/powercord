from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn import Config, Server

from app.api.api_logging import ApiAccessLoggerMiddleware
from app.api.dependencies import api_scope_required
from app.common.gsm_loader import load_env

load_env()

# Global reference to the bot instance
bot_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the FastAPI app."""
    # Startup: logic here if needed
    yield
    # Shutdown: logic here if needed


class AdminNetworkRestrictionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path not in ["/docs", "/openapi.json", "/static"]:
            client_ip = request.client.host if request.client else ""
            if client_ip not in ("127.0.0.1", "::1", "localhost", "testclient"):
                return JSONResponse(status_code=403, content={"detail": "Forbidden: External access denied"})
        return await call_next(request)


api = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
api.add_middleware(AdminNetworkRestrictionMiddleware)
api.add_middleware(ApiAccessLoggerMiddleware)

# APIRouter for endpoints that require authentication
api_router = APIRouter(dependencies=[Depends(api_scope_required("global"))])

# Resolve static directory relative to this file
# app/bot/internal_server.py -> parents[1] = app
static_dir = Path(__file__).resolve().parents[1] / "static"

api.mount("/static", StaticFiles(directory=static_dir), name="static")


@api.get("/openapi.json", include_in_schema=False, dependencies=[Depends(api_scope_required("global"))])
async def get_openapi_endpoint():
    return JSONResponse(get_openapi(title=api.title, version=api.version, routes=api.routes))


@api.get("/docs", include_in_schema=False, dependencies=[Depends(api_scope_required("global"))])
async def custom_swagger_ui_html(request: Request):
    token = request.query_params.get("token")
    openapi_url = f"/openapi.json?token={token}" if token else "/openapi.json"

    return get_swagger_ui_html(
        openapi_url=openapi_url,
        title=api.title + " - Swagger UI",
        oauth2_redirect_url=api.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger.css?v=fixed9",
    )


def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot


@api_router.get("/stats")
async def get_stats():
    """Returns system and bot statistics."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # System Stats
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()

    # Bot Stats
    guild_count = len(bot_instance.guilds)
    user_count = sum(guild.member_count for guild in bot_instance.guilds)
    latency = round(bot_instance.latency * 1000) if bot_instance.latency else 0

    return {
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2),
        },
        "bot": {
            "guilds": guild_count,
            "users": user_count,
            "latency": latency,
        },
    }


@api_router.get("/logs")
async def get_logs(limit: int = 50):
    """Returns the last N lines of the log file."""
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_file = log_dir / "powercord.log"

    if not log_file.exists():
        return {"logs": ["Log file not found."]}

    try:
        # Simple implementation for now: read all lines and take last N
        # For very large logs, we might want to seek from end.
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return {"logs": lines[-limit:]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {e}"]}


@api_router.get("/user/{user_id}/guilds/{guild_id}/roles")
async def get_user_guild_roles(user_id: int, guild_id: int):
    """Returns a list of role IDs for a user in a specific guild."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    guild = bot_instance.get_guild(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")

    member = guild.get_member(user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in guild")

    # member.roles includes the @everyone role
    return {"roles": [str(role.id) for role in member.roles]}


@api_router.get("/guilds/{guild_id}/roles")
async def get_guild_roles(guild_id: int):
    """Returns all roles for a specific guild."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    guild = bot_instance.get_guild(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")

    roles = [{"id": str(r.id), "name": r.name, "color": str(r.color)} for r in guild.roles if r.name != "@everyone"]
    # sort by name for better UX
    roles.sort(key=lambda x: x["name"].lower())
    return {"roles": roles}


@api_router.get("/user/{user_id}/admin_guilds")
async def get_user_admin_guilds(user_id: int):
    """Returns a list of guilds where the user has Administrator permissions."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import AdminUser

    # Check if user is a global Powercord Admin
    engine = init_connection_engine()
    is_global_admin = False
    with Session(engine) as session:
        admin_check = session.exec(select(AdminUser).where(AdminUser.user_id == user_id)).first()
        if admin_check:
            is_global_admin = True

    admin_guilds = []
    for guild in bot_instance.guilds:
        member = guild.get_member(user_id)
        if is_global_admin or (member and member.guild_permissions.administrator):
            admin_guilds.append(
                {
                    "id": str(guild.id),
                    "name": guild.name,
                    "icon": guild.icon.key
                    if getattr(guild, "icon", None) and hasattr(guild.icon, "key")
                    else (guild.icon.url if getattr(guild, "icon", None) else None),
                }
            )

    # Sort guilds nicely
    admin_guilds.sort(key=lambda x: x["name"].lower())
    return {"guilds": admin_guilds}


@api_router.post("/extensions/{name}/reload")
async def reload_extension(name: str):
    """Reloads a specific extension."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    cog_path = f"app.extensions.{name}.cog"
    try:
        cog_file = Path(__file__).resolve().parents[1] / "extensions" / name / "cog.py"
        if not cog_file.exists():
            return {"status": "success", "message": f"Extension '{name}' reloaded (no cog to sync)."}

        # Check if extension is loaded
        if cog_path in bot_instance.extensions:
            bot_instance.reload_extension(cog_path)
        else:
            bot_instance.load_extension(cog_path)

        # Trigger rollout to sync commands
        await bot_instance.rollout_application_commands()

        return {"status": "success", "message": f"Extension '{name}' reloaded."}
    except Exception as e:
        logging.error(f"Failed to reload extension {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from None


@api_router.post("/extensions/{name}/unload")
async def unload_extension(name: str):
    """Unloads a specific extension and syncs commands."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    cog_path = f"app.extensions.{name}.cog"
    try:
        cog_file = Path(__file__).resolve().parents[1] / "extensions" / name / "cog.py"
        if not cog_file.exists():
            return {"status": "success", "message": f"Extension '{name}' unloaded (no cog to sync)."}

        if cog_path in bot_instance.extensions:
            bot_instance.unload_extension(cog_path)
            # Trigger rollout to remove commands from Discord
            await bot_instance.rollout_application_commands()
            return {"status": "success", "message": f"Extension '{name}' unloaded."}
        else:
            return {"status": "success", "message": f"Extension '{name}' was not loaded."}
    except Exception as e:
        logging.error(f"Failed to unload extension {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from None


@api_router.get("/extensions/{name}/hotload-check")
async def hotload_check(name: str):
    """Checks if a cog has preload requirements that prevent hot-loading."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Access the powerloader cog's preload map to check for hot-load restrictions
    powerloader = bot_instance.get_cog("AppPowerLoader")
    if powerloader and hasattr(powerloader, "_hotload_caution"):
        requires_restart = powerloader._hotload_caution(name)
    else:
        # If powerloader isn't available, assume safe to hot-load
        requires_restart = False

    return {"requires_restart": requires_restart}


@api_router.post("/bot/restart")
async def restart_bot():
    """Gracefully shuts down the bot process. Relies on the process manager to restart it."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    logging.warning("Bot restart requested via admin UI. Shutting down...")

    # Close the bot connection gracefully before exiting
    await bot_instance.close()
    sys.exit(0)


@api_router.post("/config/reload")
async def reload_config(payload: dict):
    """Reloads bot configuration for a guild."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    guild_id = payload.get("guild_id")
    if guild_id is None:
        raise HTTPException(status_code=400, detail="guild_id required")

    logging.info(f"Received config reload request for guild {guild_id}")
    # Here you would trigger any specific reload logic for the bot
    # For now, we just log it as the bot might re-read DB on next event
    return {"status": "success", "message": f"Config reload triggered for guild {guild_id}"}


@api_router.post("/examples/counters")
async def toggle_example_counters(payload: dict):
    """Toggles the example counters in the ExamplesCog."""
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    action = payload.get("action")
    if action not in ("start", "stop"):
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'start' or 'stop'.")

    cog = bot_instance.get_cog("ExamplesCog")
    if not cog:
        raise HTTPException(status_code=404, detail="ExamplesCog not found. Is the 'example' extension loaded?")

    try:
        if action == "start":
            if hasattr(cog, "start_counters"):
                cog.start_counters()
                message = "Example counters started."
            else:
                raise HTTPException(status_code=500, detail="ExamplesCog does not have 'start_counters' method.")
        else:
            if hasattr(cog, "stop_counters"):
                cog.stop_counters()
                message = "Example counters stopped."
            else:
                raise HTTPException(status_code=500, detail="ExamplesCog does not have 'stop_counters' method.")

        return {"status": "success", "message": message}
    except Exception as e:
        logging.error(f"Failed to toggle example counters: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from None


# Finally include the router on the main api object
api.include_router(api_router)


async def start_bot_api(bot):
    """Starts the internal FastAPI server."""
    set_bot_instance(bot)

    port = int(os.getenv("POWERCORD_BOT_API_PORT", 8001))
    # Force localhost to avoid Windows firewall issues and listen on the loopback interface
    host = "127.0.0.1"

    # We use loop="none" because we are already running inside the Nextcord event loop
    config = Config(app=api, host=host, port=port, log_level="warning", access_log=False, loop="none")
    server = Server(config)

    logging.info(f"Starting Bot Internal API on {host}:{port}")
    try:
        await server.serve()
    except Exception as e:
        logging.error(f"Failed to start Bot Internal API: {e}", exc_info=True)
