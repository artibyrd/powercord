import json
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class ApiAccessLoggerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger_name="api_access"):
        super().__init__(app)
        # Create a dedicated logger that avoids duplicate formatting
        self.logger = logging.getLogger(logger_name)
        # If no handlers exist, add one
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            # Raw string output so JSON isn't messed up
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
            # Prevent propagating to root logger to avoid rich console formatting interference
            self.logger.propagate = False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            execution_time = time.time() - start_time

            identity = getattr(request.state, "user_identity", "unauthenticated")

            log_data = {
                "event": "api_access",
                "timestamp": start_time,
                "method": request.method,
                "path": str(request.url.path),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "status_code": status_code,
                "execution_time_ms": round(execution_time * 1000, 2),
                "identity": identity,
            }

            self.logger.info(json.dumps(log_data))

        return response  # type: ignore
