"""Admin bulk tools — broadcast + bulk credit."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.keyboards.admin_kb import bulk_menu_kb
from bot.models.purchase import Purchase
from bot.models.user import User
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.services.wallet import credit
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_bulk")

MAX_BROADCAST = 5000


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


async def _get_user_tg_ids(kind: str) -> list[int]:
    """Fetch tg_ids (no ORM objects)."""
    async with SessionLocal() as s:
        if kind == "all":
            r = await s.execute(
                select(User.tg_id)
                .where(User.is_blocked == False)  # noqa: E712
                .limit(MAX_BROADCAST)
            )
        elif kind == "active":
            since = datetime.now(timezone.utc) - timedelta(days=7)
            subq = (
                select(Purchase.user_id)
                .where(Purchase.purchased_at >= since)
                .scalar_subquery()
            )
            r = await s.execute(
                select(User.tg_id)
                .where(
                    User.is_blocked == False,  # noqa: E712
                    User.id.in_(subq),
                )
                .limit(MAX_BROADCAST)
            )
        else:
            return []
        return [row[0] for row in r.all()]


@router.callback_query(F.data == "abulk:menu")
async def bulk_menu(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    await state.clear()
    await edit_or_send(
        cb,
        "<b>BULK TOOLS</b>\n\n"
        "mass action — သတိထားပါ",
        reply_markup=bulk_menu_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "abulk:broadcast")
async def broadcast_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    await state.update_data(bcast_kind="all")
    await state.set_state("Bulk:message")
    await edit_or_send(
        cb,
        "<b>BROADCAST — All Users</b>\n\nMessage ရိုက်ပါ:",
    )
    await cb.answer()


@router.callback_query(F.data == "abulk:bcast_active")
async def broadcast_active_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    await state.update_data(bcast_kind="active")
    await state.set_state("Bulk:message")
    await edit_or_send(
        cb,
        "<b>BROADCAST — Active 7d</b>\n\nMessage ရိုက်ပါ:",
    )
    await cb.answer()


@router.message(StateFilter("Bulk:message"), TextInput())
async def broadcast_preview(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    text = (message.text or "").strip()
    if not text or len(text) > 3500:
        await message.answer("1-3500 chars:")
        return

    data = await state.get_data()
    kind = data.get("bcast_kind", "all")

    await state.update_data(bcast_text=text)
    await state.set_state("Bulk:confirm")

    tg_ids = await _get_user_tg_ids(kind)

    await message.answer(
        f"<b>CONFIRM BROADCAST</b>\n\n"
        f"Target: {len(tg_ids)} users\n"
        f"Type: {kind}\n\n"
        f"Preview:\n{text[:300]}\n\n"
        f"Send လုပ်ရန် 'yes' ရိုက်ပါ:"
    )


@router.message(StateFilter("Bulk:confirm"), TextInput())
async def broadcast_confirm(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    if (message.text or "").strip().lower() != "yes":
        await state.clear()
        await message.answer("Cancelled.")
        return

    data = await state.get_data()
    kind = data.get("bcast_kind", "all")
    text = data.get("bcast_text")
    await state.clear()

    if not text:
        await message.answer("Data ပျောက်")
        return

    tg_ids = await _get_user_tg_ids(kind)
    await message.answer(
        f"Sending to {len(tg_ids)} users..."
    )

    sent = 0
    fail = 0

    for tg_id in tg_ids:
        try:
            await message.bot.send_message(
                chat_id=tg_id,
                text=f"<b>Announcement</b>\n\n{text}",
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail += 1
            logger.debug(f"Broadcast fail {tg_id}: {e}")

    await message.answer(
        f"<b>Broadcast Done</b>\n\n"
        f"Sent: {sent}\n"
        f"Failed: {fail}"
    )


@router.callback_query(F.data == "abulk:credit")
async def bulk_credit_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    await state.set_state("Bulk:credit_amount")
    await edit_or_send(
        cb,
        "<b>BULK CREDIT</b>\n\n"
        "Active users (7d) အားလုံးကို credit ပေးမယ်\n\n"
        "Amount (Ks) ရိုက်ပါ:",
    )
    await cb.answer()


@router.message(StateFilter("Bulk:credit_amount"), TextInput())
async def bulk_credit_amount(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    try:
        amount = int(
            (message.text or "").strip().replace(",", "")
        )
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    if amount <= 0 or amount > 100000:
        await message.answer("1-100,000:")
        return

    await state.update_data(bulk_credit=amount)
    await state.set_state("Bulk:credit_reason")
    await message.answer(
        f"{amount:,} Ks\n\nReason ရိုက်ပါ:"
    )


@router.message(StateFilter("Bulk:credit_reason"), TextInput())
async def bulk_credit_reason(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    reason = (message.text or "").strip()[:200]
    if not reason:
        await message.answer("Reason:")
        return

    data = await state.get_data()
    amount = data.get("bulk_credit", 0)
    await state.update_data(bulk_reason=reason)
    await state.set_state("Bulk:credit_confirm")

    tg_ids = await _get_user_tg_ids("active")

    await message.answer(
        f"<b>CONFIRM</b>\n\n"
        f"Users: {len(tg_ids)}\n"
        f"+{amount:,} Ks each\n"
        f"Total: {len(tg_ids) * amount:,} Ks\n\n"
        f"{reason}\n\n"
        f"'yes' ရိုက်ပါ:"
    )


@router.message(StateFilter("Bulk:credit_confirm"), TextInput())
async def bulk_credit_confirm(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    if (message.text or "").strip().lower() != "yes":
        await state.clear()
        await message.answer("Cancelled.")
        return

    data = await state.get_data()
    amount = data.get("bulk_credit", 0)
    reason = data.get("bulk_reason", "Bulk credit")
    await state.clear()

    tg_ids = await _get_user_tg_ids("active")

    sent = 0
    total = 0

    for tg_id in tg_ids:
        async with SessionLocal() as s:
            ok, _, _ = await credit(
                s,
                tg_id,
                amount,
                type_="adjust",
                note=f"Bulk: {reason}",
            )
            if ok:
                await s.commit()

        if ok:
            sent += 1
            total += amount
            try:
                await message.bot.send_message(
                    chat_id=tg_id,
                    text=(
                        f"<b>+{amount:,} Ks</b>\n\n{reason}"
                    ),
                )
                await asyncio.sleep(0.05)
            except Exception:
                pass

    await message.answer(
        f"<b>Bulk Credit Done</b>\n\n"
        f"Users: {sent}\n"
        f"Total: {total:,} Ks"
    )
