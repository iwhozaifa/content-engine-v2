"""Retry with exponential backoff and jitter, shared by the Notion and Claude services."""
import random
import time


class RetryableError(Exception):
    """Raise inside a retried call to try again. `wait` (seconds) overrides the backoff, e.g. Retry-After."""

    def __init__(self, message, wait=None):
        super().__init__(message)
        self.wait = wait


def backoff(attempt, base=1.0, cap=30.0):
    return min(cap, base * 2 ** attempt) * random.uniform(0.75, 1.25)


def with_retries(fn, attempts, sleep=time.sleep, on_retry=None):
    """Call fn() up to `attempts` times while it raises RetryableError. Re-raises the last error."""
    for attempt in range(attempts):
        try:
            return fn()
        except RetryableError as e:
            if attempt == attempts - 1:
                raise
            wait = e.wait if e.wait is not None else backoff(attempt)
            if on_retry:
                on_retry(attempt + 1, wait, e)
            sleep(wait)
