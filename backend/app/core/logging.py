import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_configured = False


def _configure_root_logger() -> None:
    """Wire the root logger to write every log line to dump.log (per rules.md) + stdout."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger; guarantees dump.log is configured first."""
    _configure_root_logger()
    return logging.getLogger(name)
