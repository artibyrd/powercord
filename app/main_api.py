import logging
import os
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from rich.logging import RichHandler

import app as powercord

powercord.setup_logging()
logging.getLogger().addHandler(RichHandler(rich_tracebacks=True))


import app.common.gsm_loader as gsecrets
from app.common.extension_loader import GadgetInspector

gsecrets.load_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    gadget_inspector = GadgetInspector()
    gadget_inspector.load_sprockets(app)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

from app.api.api_logging import ApiAccessLoggerMiddleware

app.add_middleware(ApiAccessLoggerMiddleware)

from pathlib import Path

# Resolve static directory relative to this file
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


from fastapi import Depends, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.dependencies import api_scope_required


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(api_scope_required("default"))])
async def get_openapi_endpoint():
    return JSONResponse(get_openapi(title=app.title, version=app.version, routes=app.routes))


@app.get("/docs", include_in_schema=False, dependencies=[Depends(api_scope_required("default"))])
async def custom_swagger_ui_html(req: Request):
    token = req.query_params.get("token")
    openapi_url = f"/openapi.json?token={token}" if token else "/openapi.json"

    return get_swagger_ui_html(
        openapi_url=openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger.css?v=fixed18",
    )


from pydantic import BaseModel


class ReloadConfigPayload(BaseModel):
    guild_id: int


@app.get("/", dependencies=[Depends(api_scope_required("default"))])
def read_root():
    return {"Hello": "World"}


@app.post("/reload_config", dependencies=[Depends(api_scope_required("default"))])
async def reload_config(payload: ReloadConfigPayload):
    """
    Reloads configuration for a specific guild.
    Currently just logs the request, but can be expanded to reload specific sprockets.
    """
    logging.info(f"API: Received config reload request for guild {payload.guild_id}")
    return {"status": "success", "message": f"Config reload received for guild {payload.guild_id}"}


@app.post("/restart", dependencies=[Depends(api_scope_required("default"))])
async def restart_api():
    """
    Restarts the API process gracefully.
    Usually relied upon by an external process manager to bring it back online.
    """
    logging.info("API: Received restart request. Exiting...")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "success", "message": "API restart initiated."}


import httpx
from fastapi import HTTPException

from app.api.dependencies import get_current_api_user
from app.db.db_tools import get_or_create_internal_key


@app.get("/client/guilds")
async def get_client_guilds(user: dict = Depends(get_current_api_user)):  # noqa: B008
    """
    Returns the guilds that the connected user administrates.
    Only accessible via a Client API Key.
    """
    identity = user.get("identity", "")
    if not identity.startswith("api_key_client_"):
        raise HTTPException(status_code=403, detail="Only Client API Keys can access this endpoint")

    parts = identity.split("_")
    if len(parts) < 4:
        raise HTTPException(status_code=400, detail="Malformed Client identity")

    user_id_str = parts[3]
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID in Client identity") from None

    internal_key = get_or_create_internal_key()
    is_global_admin = False

    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import AdminUser

    engine = init_connection_engine()
    with Session(engine) as session:
        if session.exec(select(AdminUser).where(AdminUser.user_id == user_id)).first():
            is_global_admin = True

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"http://127.0.0.1:8001/user/{user_id}/admin_guilds",
            headers={"Authorization": f"Bearer {internal_key}"},
            timeout=5.0,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch guilds from internal bot API")

        data = resp.json()
        data["is_global_admin"] = is_global_admin
        return data


@app.get("/client/guilds/{guild_id}/config")
async def get_client_guild_config(guild_id: int, user: dict = Depends(get_current_api_user)):  # noqa: B008
    """Returns the enabled/disabled state of extensions for a guild."""
    identity = user.get("identity", "")
    if not identity.startswith("api_key_client_"):
        raise HTTPException(status_code=403, detail="Only Client API Keys can access this endpoint")

    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.common.extension_loader import GadgetInspector
    from app.db.models import AdminUser
    from app.ui.helpers import is_gadget_enabled

    user_id = int(identity.split("_")[3])
    is_admin = False

    engine = init_connection_engine()
    with Session(engine) as session:
        if session.exec(select(AdminUser).where(AdminUser.user_id == user_id)).first():
            is_admin = True

    if guild_id == 0 and not is_admin:
        raise HTTPException(status_code=403, detail="Only Global Admins can access global config")

    inspector = GadgetInspector()
    extensions = inspector.inspect_extensions()

    config = []
    for ext_name, gadgets in extensions.items():
        if ext_name == "powerloader":
            continue

        if not gadgets:
            continue

        if guild_id == 0:
            local_enabled = any(is_gadget_enabled(0, ext_name, g) for g in gadgets)
        else:
            global_enabled = any(is_gadget_enabled(0, ext_name, g) for g in gadgets)
            if not global_enabled:
                continue
            local_enabled = any(is_gadget_enabled(guild_id, ext_name, g) for g in gadgets)

        config.append({"name": ext_name, "gadgets": gadgets, "is_enabled": local_enabled})

    return {"config": config}


@app.post("/client/guilds/{guild_id}/config/toggle")
async def toggle_client_guild_config(guild_id: int, payload: dict, user: dict = Depends(get_current_api_user)):  # noqa: B008
    """Toggles an extension for a specific guild."""
    identity = user.get("identity", "")
    if not identity.startswith("api_key_client_"):
        raise HTTPException(status_code=403, detail="Only Client API Keys can access this endpoint")

    from app.common.extension_loader import GadgetInspector
    from app.ui.helpers import notify_api_of_config_change, update_guild_extension_setting

    ext_name = payload.get("extension_name")
    is_enabled = payload.get("enabled", False)

    if not ext_name:
        raise HTTPException(status_code=400, detail="Missing extension_name")

    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import AdminUser

    user_id = int(identity.split("_")[3])
    is_admin = False

    engine = init_connection_engine()
    with Session(engine) as session:
        if session.exec(select(AdminUser).where(AdminUser.user_id == user_id)).first():
            is_admin = True

    if guild_id == 0 and not is_admin:
        raise HTTPException(status_code=403, detail="Only Global Admins can access global config")

    inspector = GadgetInspector()
    extensions = inspector.inspect_extensions()
    gadgets = extensions.get(ext_name, [])

    for g_type in gadgets:
        update_guild_extension_setting(guild_id, ext_name, g_type, is_enabled)

    if "sprocket" in gadgets:
        await notify_api_of_config_change(guild_id)

    return {"status": "success", "message": f"Toggled {ext_name} to {is_enabled}"}
