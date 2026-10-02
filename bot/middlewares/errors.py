"""Global error middleware — notify admin, clean user message."""
import logging
import time
import traceback
from datetime import datetime, timezone

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, ErrorEvent, TelegramObject

from bot.config import config

logger = logging.getLogger(__name__)


IGNORED_ERRORS = (
    "message is not modified",
    "message to edit not found",
    "there is no text in the message",
    "message can't be edited",
    "message caption is not modified",
    "query is too old",
    "query id is invalid",
    "bot was blocked by the user",
    "user is deactivated",
    "chat not found",
    "not enough rights",
    "have no rights to send a message",
    "bot was kicked",
    "voice messages are not supported",
)


_error_last_sent: dict[str, float] = {}
_ERROR_COOLDOWN = 3600.0


def _should_notify(err_key: str) -> bool:
    now = time.time()
    last = _error_last_sent.get(err_key, 0)
    if now - last < _ERROR_COOLDOWN:
        return False
    _error_last_sent[err_key] = now

    if len(_error_last_sent) > 200:
        cutoff = now - _ERROR_COOLDOWN * 2
        for k in list(_error_last_sent.keys()):
            if _error_last_sent[k] < cutoff:
                _error_last_sent.pop(k, None)

    return True


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self, handler, event: TelegramObject, data
    ):
        try:
            return await handler(event, data)
        except Exception as exc:
            err_lower = str(exc).lower()

            if any(ig in err_lower for ig in IGNORED_ERRORS):
                logger.debug(f"Ignored: {exc}")
                return None

            await self._handle(exc, event, data)
            return None

    async def _handle(self, exc: Exception, event, data):
        logger.error(f"Unhandled: {exc}", exc_info=exc)

        bot = data.get("bot")
        if bot is None or config.ADMIN_ID == 0:
            return

        err_key = f"{type(exc).__name__}:{str(exc)[:100]}"

        user_info = "?"
        try:
            from_user = getattr(event, "from_user", None)
            if from_user is not None:
                user_info = (
                    f"@{from_user.username or '?'} "
                    f"(ID: {from_user.id})"
                )
        except Exception:
            pass

        evt_text = "?"
        try:
            if getattr(event, "text", None):
                evt_text = event.text[:100]
            elif getattr(event, "data", None):
                evt_text = f"cb:{event.data[:80]}"
        except Exception:
            pass

        if _should_notify(err_key):
            tb = "".join(
                traceback.format_exception(
                    type(exc), exc, exc.__traceback__
                )
            )
            tb = tb[-800:]

            text = (
                f"<b>BOT ERROR</b>\n\n"
                f"User: {_escape_html(user_info)}\n"
                f"Event: {_escape_html(evt_text)}\n"
                f"Time: "
                f"{datetime.now(timezone.utc).strftime('%H:%M UTC')}\n\n"
                f"<b>{_escape_html(type(exc).__name__)}</b>: "
                f"{_escape_html(str(exc)[:200])}\n\n"
                f"<pre>{_escape_html(tb[:600])}</pre>"
            )

            try:
                await bot.send_message(
                    chat_id=config.ADMIN_ID, text=text
                )
            except Exception as notify_err:
                logger.error(
                    f"Admin notify failed: {notify_err}"
                )

        try:
            if isinstance(event, CallbackQuery):
                await event.answer(
                    "Error ဖြစ်နေပါတယ်။ "
                    "Admin ကို အသိပေးထားပါတယ်။",
                    show_alert=True,
                )
            elif hasattr(event, "answer"):
                await event.answer(
                    "Error ဖြစ်နေပါတယ်။ "
                    "Admin ကို အသိပေးထားပါတယ်။"
                )
        except Exception:
            pass


async def error_handler(event: ErrorEvent) -> bool:
    """Aiogram global error handler (for dp.errors)."""
    logger.error(
        f"ErrorEvent: {event.exception}", exc_info=event.exception
    )
    return True
