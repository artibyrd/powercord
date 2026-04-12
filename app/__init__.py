import logging
import os

from .bootstrap import setup_project_root

# Add the project root directory to the Python path to ensure consistent imports.
# This must be done before any local application imports.
setup_project_root()

from app.common.logger import config_logging


def setup_logging(name=None):
    # Configure logging. Use DEBUG level if the DEBUG env var is set.
    log_level = logging.DEBUG if os.getenv("POWERCORD_DEBUG", "").lower() in ("true", "1", "yes") else logging.INFO

    # Configure file logging using the shared utility
    config_logging(level=log_level, filename=name, console=True)

    # Silence verbose loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
