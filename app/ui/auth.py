# mypy: ignore-errors
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fasthtml.common import *
from fasthtml.core import APIRouter

# Add the project root directory to the Python path to ensure consistent imports
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# Create an APIRouter to group auth-related routes
auth_router = APIRouter()


# Helper to get Discord credentials
def get_discord_creds():
    client_id = os.getenv("DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    bot_token = os.getenv("DISCORD_TOKEN")
    return client_id, client_secret, bot_token


# Beforeware to protect routes that require authentication
async def auth_before(req, sess):
    auth = req.scope["auth"] = sess.get("auth", None)
    if not auth:
        return RedirectResponse("/login", status_code=303)

    user_id = int(auth.get("id", 0))

    # Re-validate global admin for /admin routes
    if req.url.path.startswith("/admin"):
        from app.ui.helpers import is_dashboard_admin

        if not is_dashboard_admin(user_id):
            # User is in session but not in DB (permissions revoked or DB wiped)
            add_toast(sess, "Your global admin privileges have been revoked.", "error")
            return RedirectResponse("/profile", status_code=303)

    # Re-validate per-guild admin for /dashboard/{guild_id} routes
    if req.url.path.startswith("/dashboard/"):
        path_parts = req.url.path.split("/")
        if len(path_parts) >= 3 and path_parts[2].isdigit():
            guild_id = path_parts[2]
            token_data = auth.get("token_data", {})
            user_access_token = token_data.get("access_token")

            if not user_access_token:
                add_toast(sess, "Session token missing. Please re-authenticate.", "error")
                return RedirectResponse("/login", status_code=303)

            from app.ui.helpers import get_admin_guilds

            try:
                admin_guilds = await get_admin_guilds(user_access_token, user_id)
                if guild_id not in admin_guilds:
                    add_toast(sess, "You do not have permission to access that server dashboard.", "error")
                    return RedirectResponse("/profile", status_code=303)
            except Exception as e:
                logging.error(f"Failed to re-validate guild {guild_id} access: {e}")
                add_toast(sess, "Error validating server access.", "error")
                return RedirectResponse("/profile", status_code=303)


@auth_router("/login")
def login(req, sess):
    """The login page, which displays a link to initiate Discord OAuth."""
    # Fetch credentials here to ensure they are loaded
    client_id, _, _ = get_discord_creds()

    if not client_id:
        logging.error("DISCORD_CLIENT_ID is not set in environment.")
        return Titled("Error", P("Application configuration error: Missing Client ID."))

    base_url = os.getenv("BASE_URL")
    if base_url:
        redirect_uri = f"{base_url}/auth/discord/callback"
    else:
        redirect_uri = str(req.url.replace(path="/auth/discord/callback", query=None))
    logging.debug(f"Generating login link with redirect_uri: {redirect_uri}")

    # Manually construct the authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": "identify guilds",
        "redirect_uri": redirect_uri,
    }
    login_link = f"https://discord.com/oauth2/authorize?{urlencode(params)}"

    # Premium Login Page UI
    login_card = Div(
        Div(
            Div(
                I(cls="fa-solid fa-bolt text-6xl text-warning mb-4 animate-pulse"),
                H1("Powercord", cls="text-5xl font-black italic tracking-tighter text-warning mb-2"),
                P("Secure Admin Dashboard", cls="text-base-content/60 text-lg mb-8"),
                A(
                    Div(
                        I(cls="fa-brands fa-discord mr-3"),
                        Span("Login with Discord"),
                        cls="flex items-center justify-center",
                    ),
                    href=login_link,
                    cls="btn btn-primary btn-lg w-full gap-2 shadow-lg hover:shadow-primary/20 hover:scale-[1.02] transition-all duration-200",
                ),
                Div(
                    P(
                        "Authorized access only. By logging in, you agree to our terms.",
                        cls="text-xs text-base-content/40 mt-8",
                    ),
                    cls="text-center",
                ),
                cls="card-body items-center text-center py-12",
            ),
            cls="card bg-base-200 shadow-2xl border border-base-content/10 backdrop-blur-sm bg-opacity-80",
        ),
        cls="max-w-md w-full",
    )

    from app.ui.page import StandardPage

    return StandardPage(
        "Login | Powercord", Div(login_card, cls="flex items-center justify-center min-h-[60vh]"), auth=None
    )


async def get_user_guilds(token: str) -> Any:
    """Fetches guilds for a user via their access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_bot_guild_ids(bot_token: str) -> set[str]:
    """Fetches guild IDs for the bot via its token."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bot {bot_token}"},
        )
        resp.raise_for_status()
        return {g["id"] for g in resp.json()}


@auth_router("/auth/discord/callback")
async def discord_callback(req, sess, code: str):
    """
    Callback URL that Discord redirects to after authentication.
    Verifies that the user is an administrator in a guild shared with the bot.
    """
    ADMIN_PERM = 1 << 3  # Administrator permission bit.
    BOT_TOKEN = os.getenv("DISCORD_TOKEN")
    CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
    CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")

    if not all([BOT_TOKEN, CLIENT_ID, CLIENT_SECRET]):
        add_toast(sess, "Application is misconfigured (missing Discord credentials).", "error")
        return RedirectResponse("/login", status_code=303)

    try:
        # The redirect_uri for the token exchange must exactly match the one used to initiate the flow.
        base_url = os.getenv("BASE_URL")
        if base_url:
            redirect_uri = f"{base_url}/auth/discord/callback"
        else:
            redirect_uri = str(req.url.replace(path="/auth/discord/callback", query=None))
        logging.debug(f"Using redirect_uri for token exchange: {redirect_uri}")

        # 1. Manually exchange the authorization code for an access token.
        token_url = "https://discord.com/api/oauth2/token"
        token_payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_payload, headers=headers)
            if token_response.status_code != 200:
                logging.error(f"Discord token exchange failed: {token_response.status_code} - {token_response.text}")
                token_response.raise_for_status()
            token_json = token_response.json()
            access_token = token_json["access_token"]

            # 2. Use the access token to fetch user information.
            user_info_url = "https://discord.com/api/users/@me"
            user_headers = {"Authorization": f"Bearer {access_token}"}
            user_response = await client.get(user_info_url, headers=user_headers)
            user_response.raise_for_status()
            user_info = user_response.json()

            # 3. Verify the user has admin permissions in a shared guild.
            if BOT_TOKEN is None:  # pragma: no cover — already guarded above
                add_toast(sess, "Application is misconfigured (missing bot token).", "error")
                return RedirectResponse("/login", status_code=303)
            user_guilds, bot_guild_ids = await asyncio.gather(
                get_user_guilds(access_token), get_bot_guild_ids(BOT_TOKEN)
            )
            is_admin_on_shared_guild = any(
                g["id"] in bot_guild_ids and (int(g["permissions"]) & ADMIN_PERM) for g in user_guilds
            )

            if is_admin_on_shared_guild:
                user_info["token_data"] = token_json

                # Check Dashboard Admin status
                from app.ui.helpers import is_dashboard_admin

                user_id = int(user_info["id"])
                user_info["is_dashboard_admin"] = is_dashboard_admin(user_id)

                sess["auth"] = user_info
                add_toast(sess, f"Welcome, {user_info.get('username')}!", "success")

                if user_info["is_dashboard_admin"]:
                    return RedirectResponse("/admin", status_code=303)
                else:
                    return RedirectResponse("/profile", status_code=303)
    except httpx.HTTPStatusError as e:
        logging.error(
            f"An HTTP error occurred during authentication: {e.response.text}",
            exc_info=True,
        )
        add_toast(sess, f"An error occurred during authentication: {e}", "error")
        return RedirectResponse("/login", status_code=303)
    except Exception as e:
        logging.error(f"An error occurred during authentication: {e}", exc_info=True)
        add_toast(sess, f"An error occurred during authentication: {e}", "error")
        return RedirectResponse("/login", status_code=303)

    add_toast(
        sess,
        "Authorization failed. You must be an administrator on a server where the bot is present.",
        "error",
    )
    return RedirectResponse("/login", status_code=303)


@auth_router("/logout")
def logout(sess):
    """Clears the session and redirects to the login page."""
    if "auth" in sess:
        del sess["auth"]
    return RedirectResponse("/login", status_code=303)


@auth_router("/dev/login")
def dev_login(sess):
    """Dev-only route: logs in as a test admin without Discord OAuth.

    Only available when the DEBUG environment variable is set.
    Creates a fake session with dashboard admin privileges so that
    automated testing tools (e.g. browser agents) can access /admin.
    """
    # Guard: only allow in development (DEBUG set or running on localhost)
    base_url = os.getenv("BASE_URL", "http://localhost:5001")
    is_local = "localhost" in base_url or "127.0.0.1" in base_url
    if not (os.getenv("DEBUG") or is_local):
        return RedirectResponse("/login", status_code=303)

    # Synthetic admin session — no real Discord token
    sess["auth"] = {
        "id": "000000000000000000",
        "username": "DevAdmin",
        "avatar": None,
        "is_dashboard_admin": True,
        "token_data": {"access_token": "dev-token"},
    }
    logging.info("DEV LOGIN: Logged in as synthetic admin user.")
    return RedirectResponse("/admin", status_code=303)
