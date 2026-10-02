"""Message helpers — edit-or-send, clean replies."""
import logging
from collections import defaultdict

from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)

logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024

_last_bot_msg: dict[int, int] = {}
_extra_msgs: dict[int, list[int]] = defaultdict(list)


async def cleanup_previous(bot, chat_id: int) -> None:
    """Delete previously tracked bot messages."""
    last = _last_bot_msg.pop(chat_id, None)
    if last:
        try:
            await bot.delete_message(chat_id, last)
        except Exception:
            pass

    for mid in _extra_msgs.pop(chat_id, []):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass


async def send_clean(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    """Delete previous bot msg, send new text msg."""
    chat_id = message.chat.id
    await cleanup_previous(message.bot, chat_id)

    kwargs = {}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup

    sent = await message.answer(text, **kwargs)
    _last_bot_msg[chat_id] = sent.message_id
    return sent


async def send_clean_photo(
    message: Message,
    photo: str,
    caption: str = "",
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    """Delete previous bot msg, send new photo msg."""
    chat_id = message.chat.id
    await cleanup_previous(message.bot, chat_id)

    kwargs = {}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup

    sent = await message.answer_photo(
        photo, caption=caption[:CAPTION_LIMIT], **kwargs
    )
    _last_bot_msg[chat_id] = sent.message_id
    return sent


async def edit_or_send(
    event: CallbackQuery | Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    photo: str | None = None,
) -> None:
    """Unified edit-or-send for callbacks and messages."""
    photo_caption = text
    text_extra: str | None = None
    if photo is not None and len(text) > CAPTION_LIMIT:
        photo_caption = text[: CAPTION_LIMIT - 3] + "..."
        text_extra = text

    if isinstance(event, CallbackQuery):
        chat_id = event.message.chat.id
        msg = event.message
        is_photo = bool(msg.photo)

        try:
            if photo is not None or is_photo:
                try:
                    await msg.delete()
                except Exception:
                    pass

                if photo is not None:
                    sent = await msg.answer_photo(
                        photo,
                        caption=photo_caption,
                        reply_markup=(
                            reply_markup
                            if text_extra is None else None
                        ),
                    )
                    _last_bot_msg[chat_id] = sent.message_id
                    if text_extra is not None:
                        sent2 = await msg.answer(
                            text_extra, reply_markup=reply_markup
                        )
                        _last_bot_msg[chat_id] = sent2.message_id
                else:
                    sent = await msg.answer(
                        text, reply_markup=reply_markup
                    )
                    _last_bot_msg[chat_id] = sent.message_id
                return

            await msg.edit_text(text, reply_markup=reply_markup)
            _last_bot_msg[chat_id] = msg.message_id
            return

        except Exception as e:
            logger.debug(
                f"edit_or_send fallback: {type(e).__name__}"
            )
            try:
                await msg.delete()
            except Exception:
                pass

            if photo is not None:
                sent = await msg.answer_photo(
                    photo, caption=photo_caption
                )
                _last_bot_msg[chat_id] = sent.message_id
                if text_extra is not None:
                    sent2 = await msg.answer(
                        text_extra, reply_markup=reply_markup
                    )
                    _last_bot_msg[chat_id] = sent2.message_id
            else:
                sent = await msg.answer(
                    text, reply_markup=reply_markup
                )
                _last_bot_msg[chat_id] = sent.message_id
            return

    if photo is not None:
        await send_clean_photo(
            event, photo, photo_caption,
            reply_markup=reply_markup,
        )
        if text_extra is not None:
            await send_clean(event, text_extra)
    else:
        await send_clean(event, text, reply_markup=reply_markup)


def track_extra(chat_id: int, msg_id: int) -> None:
    """Track additional bot messages (files) for cleanup."""
    _extra_msgs[chat_id].append(msg_id)


def clear_tracking(chat_id: int | None = None) -> None:
    """Clear tracking dicts (memory safety)."""
    if chat_id is None:
        _last_bot_msg.clear()
        _extra_msgs.clear()
    else:
        _last_bot_msg.pop(chat_id, None)
        _extra_msgs.pop(chat_id, None)
