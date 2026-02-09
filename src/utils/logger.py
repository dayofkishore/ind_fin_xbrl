import logging
import json
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from src.utils.settings import settings


# -------------------------------------------------------------------
# JSON Log Formatter
# -------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "message": record.getMessage(),
            "environment": settings.environment,
            "project": settings.project_name,
            "python_version": settings.python_version,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


# -------------------------------------------------------------------
# Logger Factory
# -------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger  # Prevent duplicate handlers

    formatter = JsonFormatter()

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File Handler with Rotation
    log_file: Path = settings.logs_path / "application.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
