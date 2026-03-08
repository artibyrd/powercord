import logging
import logging.handlers
from pathlib import Path

import google.cloud.logging

from app.common.gsm_loader import check_gce_metadata


def log_to_file():
    log_to_file = check_gce_metadata(metadata_key="LOG_TO_FILE")
    if not log_to_file:
        # Avoid using logging here to prevent premature initialization of basicConfig
        log_to_file = True
    else:
        pass
    return log_to_file


log_path = Path(__file__).resolve().parents[1] / "logs"


def config_logging(level=logging.INFO, filename=None, console=True, gcloud=False):
    # Determine if we should log to file.
    # NOTE: This function logs a warning which triggers logging.basicConfig if no handlers exist!
    # So we must call it before clearing handlers.
    should_log_to_file = log_to_file() if filename else False

    # Clear existing handlers (including any created by the above warning)
    rootLogger = logging.getLogger()
    rootLogger.handlers = []

    logFormatter = logging.Formatter("%(asctime)s [%(threadName)s] [%(module)s] [%(levelname)s] %(message)s")
    rootLogger.setLevel(level)

    # add handling for logging to file
    if filename and should_log_to_file:
        log_path.mkdir(exist_ok=True)
        file_path = log_path / f"{filename}.log"
        fileHandler = logging.handlers.WatchedFileHandler(file_path)
        fileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(fileHandler)

    # add handling to log output to console
    if console:
        from rich.logging import RichHandler

        # RichHandler already has a nice format, so we don't need to apply the standard one to it usually,
        # but we can configure it to show the bits we want.
        rootLogger.addHandler(RichHandler(rich_tracebacks=True, markup=True))

    # add handling for Google Cloud Logging
    if gcloud:
        gClient = google.cloud.logging.Client()
        gClient.setup_logging()
