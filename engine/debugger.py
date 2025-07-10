import logging
import traceback
from functools import wraps
from typing import Callable, Any


def setup_debugger(log_file: str = "debug.log", level: int = logging.DEBUG) -> None:
    """Configure root logger for debugging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
    )


def log_exceptions(func: Callable) -> Callable:
    """Decorator to log exceptions from the wrapped function."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - simple logging helper
            logging.error("Exception in %s: %s", func.__name__, exc)
            logging.error("%s", traceback.format_exc())
            raise

    return wrapper
