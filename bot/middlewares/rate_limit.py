"""Per-user in-memory rate limit with auto cleanup."""
import logging
import time
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Sliding-window rate limit per user."""

    def __init__(
        self,
        max_events: int = 5,
        window: int = 3,
        cleanup_interval: int = 300,
    ):
        self.max_events = max_events
        self.window = window
        self._buckets: dict[int, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval

    def _maybe_cleanup(self, now: float) -> None:
        """Periodic cleanup of empty buckets."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now

        cutoff = now - self.window
        empty: list[int] = []
        for uid, bucket in self._buckets.items():
            bucket[:] = [t for t in bucket if t > cutoff]
            if not bucket:
                empty.append(uid)

        for uid in empty:
            del self._buckets[uid]

    async def __call__(
        self, handler, event: TelegramObject, data
    ):
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        now = time.time()
        self._maybe_cleanup(now)

        bucket = self._buckets[user.id]
        cutoff = now - self.window
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= self.max_events:
            logger.warning(f"Rate limit: user={user.id}")
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer(
                        "အလွန်မြန်နေပါတယ်။ ခဏစောင့်ပါ။",
                        show_alert=True,
                    )
                elif hasattr(event, "answer"):
                    await event.answer(
                        "အလွန်မြန်နေပါတယ်။ ခဏစောင့်ပါ။"
                    )
            except Exception:
                pass
            return None

        bucket.append(now)
        return await handler(event, data)
