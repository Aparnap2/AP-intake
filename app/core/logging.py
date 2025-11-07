"""
Logging configuration for the application.
"""

import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging():
    """Configure application logging."""
    # Remove default loguru handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # Add file handler for JSON structured logs
    if not Path("logs").exists():
        Path("logs").mkdir(exist_ok=True)

    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=settings.LOG_LEVEL,
        compression="zip",
    )

    # Intercept standard logging and redirect to loguru
    class InterceptHandler(logging.Handler):
        """Intercept standard logging and redirect to loguru."""

        def emit(self, record):
            """Emit log record to loguru."""
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Configure standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Configure specific loggers
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
    logging.getLogger("sqlalchemy.engine").handlers = [InterceptHandler()]
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def get_logger(name: str):
    """Get a logger instance for a specific module."""
    return logger.bind(name=name)