import time
from collections import deque
from typing import Any, Callable, Dict

MAX_REQUESTS_PER_MINUTE = 60
MAX_TOKENS_PER_MINUTE = 100000
RATE_LIMIT_WINDOW_SECONDS = 60
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_BACKOFF_MULTIPLIER = 2.0


class RateLimiter:
    """Rolling window rate limiter tracking requests and estimated token usage."""

    def __init__(self):
        self.requests = deque()

    def _evict_old_entries(self, now: float):
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        while self.requests and self.requests[0][0] <= cutoff:
            self.requests.popleft()

    def wait_if_needed(self, estimated_tokens: int = 0):
        """Blocks if the rolling request or token limits are exceeded."""
        while True:
            now = time.time()
            self._evict_old_entries(now)

            # Check request rate limit
            if len(self.requests) >= MAX_REQUESTS_PER_MINUTE:
                oldest_time, _ = self.requests[0]
                sleep_time = oldest_time + RATE_LIMIT_WINDOW_SECONDS - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    self.requests.popleft()
                continue

            # Check token rate limit
            current_tokens = sum(r[1] for r in self.requests)
            if current_tokens + estimated_tokens > MAX_TOKENS_PER_MINUTE:
                # Calculate minimum wait time
                temp_requests = list(self.requests)
                needed_tokens = current_tokens + estimated_tokens - MAX_TOKENS_PER_MINUTE
                freed_tokens = 0
                sleep_time = 0
                for req_time, req_tokens in temp_requests:
                    freed_tokens += req_tokens
                    sleep_time = req_time + RATE_LIMIT_WINDOW_SECONDS - now
                    if freed_tokens >= needed_tokens:
                        break
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    self.requests.popleft()
                continue

            break

        self.requests.append((time.time(), estimated_tokens))

    def get_stats(self) -> Dict:
        """Returns statistics about the current rate limit window."""
        now = time.time()
        self._evict_old_entries(now)
        return {
            "requests_in_window": len(self.requests),
            "tokens_in_window": sum(r[1] for r in self.requests),
            "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
        }


default_rate_limiter = RateLimiter()


def call_with_retry(
    fn: Callable, *args, estimated_tokens: int = 0, **kwargs
) -> Any:
    """Executes a function with rolling rate limit wait and automatic exponential backoff retries."""
    last_exc = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        default_rate_limiter.wait_if_needed(estimated_tokens)
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            exc_str = str(exc).lower()
            is_rate_limit = False
            if hasattr(exc, "status_code") and exc.status_code == 429:
                is_rate_limit = True
            elif (
                "429" in exc_str
                or "rate limit" in exc_str
                or "too many requests" in exc_str
            ):
                is_rate_limit = True

            if is_rate_limit:
                last_exc = exc
                delay = RETRY_BASE_DELAY_SECONDS * (RETRY_BACKOFF_MULTIPLIER**attempt)
                time.sleep(delay)
            else:
                raise exc

    raise RuntimeError(
        f"Rate limit retry attempts exhausted ({RETRY_MAX_ATTEMPTS} attempts). Last error: {last_exc}"
    ) from last_exc
