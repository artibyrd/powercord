# mypy: ignore-errors
from __future__ import annotations

import functools
import inspect

from fasthtml.common import P

import app.ui.helpers as helpers


def require_admin(f):
    """Defense-in-depth decorator verifying dashboard admin session for /admin/* routes."""
    original_sig = inspect.signature(f)

    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        sess = kwargs.get("sess")
        if sess is None:
            if "sess" in original_sig.parameters:
                idx = list(original_sig.parameters.keys()).index("sess")
                if idx < len(args):
                    sess = args[idx]
            elif len(args) > len(original_sig.parameters):
                sess = args[-1]
        if not sess:
            for arg in args:
                if hasattr(arg, "session"):
                    sess = getattr(arg, "session", {})
                    break

        auth = (sess or {}).get("auth", {}) if isinstance(sess, dict) else {}
        user_id = auth.get("id")
        is_admin = False
        if user_id is not None:
            try:
                import sys

                is_admin_fn = getattr(
                    sys.modules.get("app.ui.helpers"), "is_dashboard_admin", helpers.is_dashboard_admin
                )
                is_admin = is_admin_fn(int(user_id))
            except (ValueError, TypeError):
                pass
        if not is_admin:
            return P("Forbidden", cls="text-error")

        f_args = args[: len(original_sig.parameters)] if "sess" not in original_sig.parameters else args
        f_kwargs = (
            {k: v for k, v in kwargs.items() if k in original_sig.parameters}
            if "sess" not in original_sig.parameters
            else kwargs
        )
        return await f(*f_args, **f_kwargs)

    if "sess" not in original_sig.parameters:
        params = list(original_sig.parameters.values())
        params.append(inspect.Parameter("sess", inspect.Parameter.POSITIONAL_OR_KEYWORD))
        wrapper.__signature__ = original_sig.replace(parameters=params)
    else:
        wrapper.__signature__ = original_sig

    return wrapper
