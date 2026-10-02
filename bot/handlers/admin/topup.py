"""Admin — topup review (approve / reject / adjust)."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.config import config
from bot.keyboards.admin_kb import (
    topup_adjust_back_kb,
    topup_approve_confirm_kb,
    topup_detail_kb,
    topup_list_kb,
    topup_reject_confirm_kb,
    topup_reject_reasons_kb,
)
from bot.models.user import User
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.services.topup_service import (
    get_topup,
    list_pending,
    mark_approved,
    mark_rejected,
)
from bot.services.wallet import credit
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_topup")


REJECT_REASONS = {
    "r1": "Screenshot မရှင်း",
    "r2": "Amount မမှန်",
    "r3": "Duplicate",
    "rc": None,
}


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


async def _get_user(session, user_id: int) -> User | None:
    r = await session.execute(
        select(User).where(User.id == user_id)
    )
    return r.scalar_one_or_none()


@router.callback_query(F.data == "admin:topups")
async def show_topups(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        topups = await list_pending(s, limit=20)

    if not topups:
        text = (
            "<b>TOPUP REQUESTS</b>\n\n"
            "Pending မရှိပါ။"
        )
    else:
        text = (
            f"<b>TOPUP REQUESTS ({len(topups)})</b>\n\n"
            f"Pending"
        )

    await edit_or_send(
        cb, text, reply_markup=topup_list_kb(topups)
    )
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:tp:\d+$"))
async def show_detail(cb: CallbackQuery):
    if not await _ok(cb):
        return

    topup_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        t = await get_topup(s, topup_id)
        if t is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        user = await _get_user(s, t.user_id)

        user_username = user.username if user else None
        user_tg_id = user.tg_id if user else 0
        user_balance = user.balance if user else 0

        amount = t.amount
        method = t.method
        account = t.account_number
        created_at = t.created_at
        screenshot_id = t.screenshot_file_id

    uname = user_username or "user"
    masked = f"@{uname[:1]}***"

    created_str = (
        created_at.strftime("%d %b %H:%M")
        if created_at else "—"
    )

    text = (
        f"<b>#TP-{topup_id:03d}</b>\n\n"
        f"{masked} (ID: {user_tg_id})\n"
        f"{amount:,} Ks\n"
        f"{method.upper()} — {account}\n"
        f"{created_str}\n\n"
        f"Balance: {user_balance:,} Ks"
    )

    try:
        await cb.message.answer_photo(
            photo=screenshot_id,
            caption=text,
            reply_markup=topup_detail_kb(topup_id),
        )
        try:
            await cb.message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Detail photo: {e}")
        await edit_or_send(
            cb, text, reply_markup=topup_detail_kb(topup_id)
        )

    await cb.answer()


@router.callback_query(F.data.startswith("adm:tp:ap:"))
async def approve_router(cb: CallbackQuery):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")

    if len(parts) == 4:
        topup_id = int(parts[3])

        async with SessionLocal() as s:
            t = await get_topup(s, topup_id)
            if t is None:
                await cb.answer("မတွေ့ပါ", show_alert=True)
                return
            user = await _get_user(s, t.user_id)

            amount = t.amount
            old_bal = user.balance if user else 0

        new_bal = old_bal + amount

        try:
            await cb.message.edit_caption(
                caption=(
                    f"<b>APPROVE?</b>\n\n"
                    f"#TP-{topup_id:03d}\n"
                    f"{amount:,} Ks\n\n"
                    f"Balance\n"
                    f"{old_bal:,} -> {new_bal:,} Ks"
                ),
                reply_markup=topup_approve_confirm_kb(topup_id),
            )
        except Exception:
            pass
        await cb.answer()
        return

    if len(parts) == 5 and parts[3] == "yes":
        topup_id = int(parts[4])
        await _do_approve(cb, topup_id)


async def _do_approve(cb: CallbackQuery, topup_id: int):
    async with SessionLocal() as s:
        t = await get_topup(s, topup_id)
        if t is None or t.status != "pending":
            await cb.answer("ပြီးသား", show_alert=True)
            return

        user = await _get_user(s, t.user_id)
        if user is None:
            await cb.answer("User မတွေ့", show_alert=True)
            return

        amount = t.amount
        user_tg_id = user.tg_id
        user_username = user.username

        ok, new_balance, msg = await credit(
            s,
            tg_id=user_tg_id,
            amount=amount,
            type_="topup",
            reference_id=topup_id,
            note=f"Topup #{topup_id} approve",
        )
        if not ok:
            await s.rollback()
            await cb.answer(msg, show_alert=True)
            return

        await mark_approved(
            s, topup_id, admin_id=cb.from_user.id
        )
        await s.commit()

    try:
        await cb.bot.send_message(
            chat_id=user_tg_id,
            text=(
                f"<b>{amount:,} Ks ဖြည့်ပြီး</b>\n\n"
                f"Balance: {new_balance:,} Ks"
            ),
        )
    except Exception as e:
        logger.error(f"User notify: {e}")

    try:
        uname = user_username or "user"
        masked = f"@{uname[:1]}***"
        await cb.bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=(
                f"<b>Topup အောင်မြင်ပါသည်</b>\n\n"
                f"{masked} — {amount:,} Ks"
            ),
        )
    except Exception as e:
        logger.warning(f"Public post: {e}")

    try:
        await cb.message.edit_caption(
            caption=(
                f"<b>APPROVED</b>\n\n"
                f"#TP-{topup_id:03d}\n"
                f"+{amount:,} Ks\n"
                f"Balance: {new_balance:,} Ks\n\n"
                f"Public post — OK\n"
                f"User notified — OK"
            ),
            reply_markup=None,
        )
    except Exception:
        pass

    await cb.answer("Approved")


@router.callback_query(F.data.startswith("adm:tp:rj:"))
async def reject_router(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")

    if len(parts) == 4:
        topup_id = int(parts[3])
        try:
            await cb.message.edit_caption(
                caption=(
                    f"<b>REJECT REASON</b>\n\n"
                    f"#TP-{topup_id:03d}"
                ),
                reply_markup=topup_reject_reasons_kb(topup_id),
            )
        except Exception:
            pass
        await cb.answer()
        return

    if len(parts) == 5 and parts[3] == "rc":
        topup_id = int(parts[4])
        await state.update_data(reject_topup_id=topup_id)
        await state.set_state("AdminReject:custom")

        try:
            await cb.message.edit_caption(
                caption=(
                    "<b>Custom Reject Reason</b>\n\n"
                    "User ဆီ ပို့မယ့် message ရိုက်ပါ:"
                ),
                reply_markup=topup_adjust_back_kb(topup_id),
            )
        except Exception:
            pass
        await cb.answer()
        return

    if len(parts) == 5:
        code = parts[3]
        topup_id = int(parts[4])
        reason = REJECT_REASONS.get(code)

        if reason is None:
            await cb.answer("Invalid", show_alert=True)
            return

        try:
            await cb.message.edit_caption(
                caption=(
                    f"<b>REJECT?</b>\n\n"
                    f"#TP-{topup_id:03d}\n"
                    f"{reason}\n\n"
                    f"User ဆီ message ပို့မည်။"
                ),
                reply_markup=topup_reject_confirm_kb(
                    topup_id, code
                ),
            )
        except Exception:
            pass
        await cb.answer()
        return

    if len(parts) >= 6 and parts[3] == "ok":
        code = parts[4]
        topup_id = int(parts[5])
        reason = REJECT_REASONS.get(code)

        if reason is None:
            await cb.answer("Invalid", show_alert=True)
            return

        await _do_reject(cb, topup_id, reason)


async def _do_reject(
    cb: CallbackQuery, topup_id: int, reason: str
):
    async with SessionLocal() as s:
        t = await get_topup(s, topup_id)
        if t is None or t.status != "pending":
            await cb.answer("Invalid", show_alert=True)
            return

        amount = t.amount
        await mark_rejected(
            s, topup_id, admin_id=cb.from_user.id, reason=reason
        )
        user = await _get_user(s, t.user_id)
        user_tg_id = user.tg_id if user else None

    if user_tg_id:
        try:
            from aiogram.types import (
                InlineKeyboardButton,
                InlineKeyboardMarkup,
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="ပြန်လုပ်မယ်",
                        callback_data="topup:start",
                    )],
                ]
            )
            await cb.bot.send_message(
                chat_id=user_tg_id,
                text=(
                    f"<b>Topup ပယ်ဖျက်ပါသည်</b>\n\n"
                    f"#TP-{topup_id:03d}\n"
                    f"{amount:,} Ks\n\n"
                    f"Reason:\n{reason}"
                ),
                reply_markup=kb,
            )
        except Exception as e:
            logger.error(f"Reject notify: {e}")

    try:
        await cb.message.edit_caption(
            caption=(
                f"<b>REJECTED</b>\n\n"
                f"#TP-{topup_id:03d}\n"
                f"{reason}\n\n"
                f"User notified — OK"
            ),
            reply_markup=None,
        )
    except Exception:
        pass

    await cb.answer("Rejected")


@router.message(StateFilter("AdminReject:custom"), TextInput())
async def reject_custom_input(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    data = await state.get_data()
    topup_id = data.get("reject_topup_id")
    if not topup_id:
        await state.clear()
        return

    reason = (message.text or "").strip()[:200]
    if not reason:
        await message.answer("Reason ရိုက်ပါ:")
        return

    await state.clear()

    async with SessionLocal() as s:
        t = await get_topup(s, topup_id)
        if t is None or t.status != "pending":
            await message.answer("ပြီးသား")
            return

        await mark_rejected(
            s,
            topup_id,
            admin_id=message.from_user.id,
            reason=reason,
        )
        user = await _get_user(s, t.user_id)
        user_tg_id = user.tg_id if user else None

    if user_tg_id:
        try:
            await message.bot.send_message(
                chat_id=user_tg_id,
                text=(
                    f"<b>Topup ပယ်ဖျက်ပါသည်</b>\n\n"
                    f"#TP-{topup_id:03d}\n"
                    f"{reason}"
                ),
            )
        except Exception:
            pass

    await message.answer(
        f"<b>REJECTED</b>\n\n"
        f"#TP-{topup_id:03d}\n"
        f"{reason}"
    )


@router.callback_query(F.data.startswith("adm:tp:adj:"))
async def adjust_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    parts = cb.data.split(":")
    if len(parts) != 4:
        return

    topup_id = int(parts[3])

    async with SessionLocal() as s:
        t = await get_topup(s, topup_id)

    if t is None:
        await cb.answer("မတွေ့ပါ", show_alert=True)
        return

    await state.update_data(adjust_topup_id=topup_id)
    await state.set_state("AdminAdjust:amount")

    try:
        await cb.message.edit_caption(
            caption=(
                f"<b>ADJUST AMOUNT</b>\n\n"
                f"#TP-{topup_id:03d}\n"
                f"Requested: {t.amount:,} Ks\n\n"
                f"Screenshot မှာ တကယ်ရတဲ့ amount ရိုက်ပါ:"
            ),
            reply_markup=topup_adjust_back_kb(topup_id),
        )
    except Exception:
        pass
    await cb.answer()


@router.message(StateFilter("AdminAdjust:amount"), TextInput())
async def adjust_input(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    try:
        new_amount = int(
            (message.text or "").strip().replace(",", "")
        )
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    if new_amount <= 0:
        await message.answer("0 ထက် ကြီး:")
        return

    data = await state.get_data()
    topup_id = data.get("adjust_topup_id")
    if not topup_id:
        await state.clear()
        return

    await state.clear()

    async with SessionLocal() as s:
        t = await get_topup(s, topup_id)
        if t is None or t.status != "pending":
            await message.answer("ပြီးသား")
            return

        user = await _get_user(s, t.user_id)
        if user is None:
            await message.answer("User မတွေ့")
            return

        user_tg_id = user.tg_id
        user_username = user.username
        old_amount = t.amount

        ok, new_balance, msg = await credit(
            s,
            tg_id=user_tg_id,
            amount=new_amount,
            type_="topup",
            reference_id=topup_id,
            note=(
                f"Topup #{topup_id} adjust "
                f"(orig {old_amount})"
            ),
        )
        if not ok:
            await s.rollback()
            await message.answer(msg)
            return

        await mark_approved(
            s,
            topup_id,
            admin_id=message.from_user.id,
            adjusted=new_amount,
        )
        await s.commit()

    try:
        await message.bot.send_message(
            chat_id=user_tg_id,
            text=(
                f"<b>{new_amount:,} Ks ဖြည့်ပြီး</b>\n\n"
                f"Balance: {new_balance:,} Ks"
            ),
        )
    except Exception:
        pass

    try:
        uname = user_username or "user"
        masked = f"@{uname[:1]}***"
        await message.bot.send_message(
            chat_id=config.NOTICE_CHAT_ID,
            text=(
                f"<b>Topup အောင်မြင်ပါသည်</b>\n\n"
                f"{masked} — {new_amount:,} Ks"
            ),
        )
    except Exception:
        pass

    await message.answer(
        f"<b>ADJUSTED & APPROVED</b>\n\n"
        f"#TP-{topup_id:03d}\n"
        f"Original: {old_amount:,} Ks\n"
        f"Adjusted: {new_amount:,} Ks\n"
        f"Balance: {new_balance:,} Ks"
    )
