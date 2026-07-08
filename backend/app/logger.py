import logging
import sys
import os
from pathlib import Path

# Create logs folder if it doesn't exist (only in local dev)
if not os.environ.get("VERCEL"):
    try:
        Path("logs").mkdir(exist_ok=True)
    except Exception:
        pass

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger that writes to:
    - Terminal (console handler) always.
    - logs/app.log file (file handler) only if not on Vercel/read-only env.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # ── TERMINAL HANDLER ───────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # ── FILE HANDLER ───────────────────────────────────────────────────────
    if not os.environ.get("VERCEL"):
        try:
            file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_format = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger