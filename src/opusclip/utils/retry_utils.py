"""
Generic retry decorator for transient failures.

Provides :func:`with_retry`, a configurable exponential-backoff decorator
intended for network calls and external API requests.
"""

import time
import functools
from typing import Callable, TypeVar, Any

T = TypeVar("T")


def with_retry(
    attempts: int = 3,
    delay_s: float = 2.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff.

    The decorated callable is executed up to *attempts* times. After each
    failure the sleep duration is multiplied by *backoff_factor*. If all
    attempts are exhausted the last exception propagates to the caller.

    Args:
        attempts: Total number of attempts (must be ≥ 1).
        delay_s: Initial sleep duration in seconds after the first failure.
        backoff_factor: Multiplier applied to *delay_s* after every failure.
        exceptions: Tuple of exception types that trigger a retry. Exceptions
            not listed here propagate immediately without retrying.

    Returns:
        A decorator that wraps the target callable with retry logic.

    Example::

        @with_retry(attempts=3, delay_s=1.0, exceptions=(IOError,))
        def fetch() -> str:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay_s
            last_exc: Exception = RuntimeError("No attempts made")
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
            raise last_exc

        return wrapper

    return decorator
