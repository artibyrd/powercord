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
