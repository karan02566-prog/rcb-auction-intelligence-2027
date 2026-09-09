"""Centralized logging utility for the RCB Auction Intelligence Engine."""

import logging
import sys


def get_logger(name: str = "rcb_auction", level: int = logging.INFO) -> logging.Logger:
    """
    Get or create a named logger with a standard console handler.
    Prevents adding duplicate handlers if invoked multiple times.

    Args:
        name: The logger namespace (default: 'rcb_auction').
        level: Logging level threshold (default: logging.INFO).

    Returns:
        logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if the logger is already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
