import functools
import logging
from collections.abc import Callable


def handle_api_errors[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to handle common API errors with standardized logging."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except ConnectionError as e:
            logging.getLogger(__name__).error(
                f"Connection error in {func.__name__}: {e}"
            )
            raise
        except TimeoutError as e:
            logging.getLogger(__name__).error(f"Timeout error in {func.__name__}: {e}")
            raise
        except ValueError as e:
            logging.getLogger(__name__).error(f"Value error in {func.__name__}: {e}")
            raise
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Unexpected error in {func.__name__}: {e}"
            )
            raise

    return wrapper
