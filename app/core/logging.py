from loguru import logger

from app.core.config import settings


def configure_logging() -> None:
    logger.remove()
    logger.add(lambda message: print(message, end=""), level=settings.log_level)
