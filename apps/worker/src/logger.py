"""
Worker logging setup.

Provides a `get_logger(name)` factory that returns a configured logger
with file (rotating) and console handlers. Reads level and directory
from settings.
"""
import logging
from logging.handlers import RotatingFileHandler

from src.config import settings


_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_LOG_FILE = settings.log_dir / "worker.log"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT = 5


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger with file and console handlers attached.

    Handlers are attached only once per logger name to avoid duplication
    when get_logger is called multiple times.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(settings.log_level.upper())
    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Do not propagate to root to avoid duplicate logs.
    logger.propagate = False

    return logger


if __name__ == "__main__":
    log = get_logger("worker.test")
    log.debug("This is a DEBUG message.")
    log.info("This is an INFO message.")
    log.warning("This is a WARNING message.")
    log.error("This is an ERROR message.")
    print(f"\nLog file written to: {_LOG_FILE.resolve()}")