# small in memory rate limiter for the public portal routes
# it counts per client address, so it only works for a single server process
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        queue = self.calls[key]
        # forget calls that are older than the window
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()
        if len(queue) >= self.max_calls:
            retry_after = int(self.window_seconds - (now - queue[0])) + 1
            raise HTTPException(
                429,
                "Too many attempts, please try again later",
                headers={"Retry-After": str(retry_after)},
            )
        queue.append(now)

    def reset(self) -> None:
        self.calls.clear()


# 20 calls every 10 minutes is plenty for a real patient (verify + activate is 2)
portal_limiter = RateLimiter(max_calls=20, window_seconds=600)


def portal_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    portal_limiter.check(client)
