import sys
import logging

ALLOWED_LOGGING_LEVELS = ['INFO', 'DEBUG', 'WARNING', 'ERROR']
DEFAULT_LEVEL = 'INFO'


def get_logging_level(log_level: str) -> int:
    assert log_level in ALLOWED_LOGGING_LEVELS, 'Your logging level is set incorrectly'
    return getattr(logging, log_level)


def get_logger(name: str, log_level: str = DEFAULT_LEVEL) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(get_logging_level(log_level))

    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    return logger