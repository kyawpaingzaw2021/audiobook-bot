"""Admin — promo code management."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.keyboards.admin_kb import (
    back_panel_kb,
    promo_admin_kb,
    promo_confirm_kb,
    promo_delete_confirm_kb,
    promo_type_kb,
    promo_view_kb,
)
from bot.models.promo import PromoCode
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.services.promo_service import (
    create_code,
    find_code,
    list_all,
)
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_promo")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


def _promo_view_text(p: dict) -> str:
    if p["discount_type"] == "percent":
        val = f"{p['discount_value']}% off"
    else:
        val = f"{p['discount_value']:,} Ks off"

    text = (
        f"<b>{p['code']}</b>\n\n"
        f"Discount: {val}\n"
        f"Min purchase: {p['min_purchase']:,} Ks\n"
        f"Used: {p['used_count']}"
    )
    if p["max_uses"] > 0:
        text += f" / {p['max_uses']}"
    text += (
        f"\nPer user: {p['per_user_limit']}\n"
        f"Status: {'Active' if p['is_active'] else 'Off'}"
    )
    return text


@router.callback_query(F.data == "apromo:list")
async def promo_list(cb: CallbackQuery):
    if not await _ok(cb):
        return

    async with SessionLocal() as s:
        codes = await list_all(s, limit=30)

    text = (
        f"<b>PROMO CODES</b>\n\n"
        f"Total: {len(codes)}"
    )

    await edit_or_send(
        cb, text, reply_markup=promo_admin_kb(codes)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("apromo:view:"))
async def promo_view(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        promo_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        r = await s.execute(
            select(PromoCode).where(PromoCode.id == promo_id)
        )
        p = r.scalar_one_or_none()

        if p is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        p_data = {
            "id": p.id,
            "code": p.code,
            "discount_type": p.discount_type,
            "discount_value": p.discount_value,
            "min_purchase": p.min_purchase,
            "max_uses": p.max_uses,
            "used_count": p.used_count,
            "per_user_limit": p.per_user_limit,
            "is_active": p.is_active,
        }

    text = _promo_view_text(p_data)

    await edit_or_send(
        cb,
        text,
        reply_markup=promo_view_kb(
            p_data["id"], p_data["is_active"]
        ),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("apromo:toggle:"))
async def promo_toggle(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        promo_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    async with SessionLocal() as s:
        r = await s.execute(
            select(PromoCode).where(PromoCode.id == promo_id)
        )
        p = r.scalar_one_or_none()

        if p is None:
            await cb.answer("မတွေ့ပါ", show_alert=True)
            return

        p.is_active = not p.is_active
        await s.commit()

        p_data = {
            "id": p.id,
            "code": p.code,
            "discount_type": p.discount_type,
            "discount_value": p.discount_value,
            "min_purchase": p.min_purchase,
            "max_uses": p.max_uses,
            "used_count": p.used_count,
            "per_user_limit": p.per_user_limit,
            "is_active": p.is_active,
        }

    text = _promo_view_text(p_data)

    await edit_or_send(
        cb,
        text,
        reply_markup=promo_view_kb(
            p_data["id"], p_data["is_active"]
        ),
    )
    await cb.answer("Toggled")


@router.callback_query(F.data.startswith("apromo:del:yes:"))
async def promo_del_yes(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        promo_id = int(cb.data.split(":")[3])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    from sqlalchemy import delete

    async with SessionLocal() as s:
        await s.execute(
            delete(PromoCode).where(PromoCode.id == promo_id)
        )
        await s.commit()
        codes = await list_all(s)

    await cb.answer("Deleted")

    await edit_or_send(
        cb,
        f"<b>PROMO CODES</b>\n\n"
        f"Total: {len(codes)}",
        reply_markup=promo_admin_kb(codes),
    )


@router.callback_query(F.data.regexp(r"^apromo:del:\d+$"))
async def promo_del(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        promo_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    await edit_or_send(
        cb,
        f"<b>Code ဖျက်မလား?</b>\n\n"
        f"#promo-{promo_id}\n\n"
        f"ပြန်မရနိုင်ပါ",
        reply_markup=promo_delete_confirm_kb(promo_id),
    )
    await cb.answer()


@router.callback_query(F.data == "apromo:new")
async def promo_new(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    await state.clear()
    await state.set_state("AdminPromo:code")

    await edit_or_send(
        cb,
        "<b>PROMO CODE အသစ်</b>\n\n"
        "Code ရိုက်ပါ (A-Z, 0-9, max 30):\n"
        "ဥပမာ: <code>WELCOME100</code>",
        reply_markup=back_panel_kb(),
    )
    await cb.answer()


@router.message(StateFilter("AdminPromo:code"), TextInput())
async def promo_new_code(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    code = (message.text or "").strip().upper()
    if not code or len(code) > 30:
        await message.answer("1-30 chars:")
        return
    if not code.replace("_", "").isalnum():
        await message.answer("A-Z, 0-9, underscore ပဲ:")
        return

    async with SessionLocal() as s:
        exists = await find_code(s, code)

    if exists is not None:
        await message.answer("Code ရှိပြီးသား:")
        return

    await state.update_data(promo_code=code)
    await state.set_state("AdminPromo:type")

    await message.answer(
        f"Code: <code>{code}</code>\n\n"
        f"Discount type ရွေးပါ:",
        reply_markup=promo_type_kb(),
    )


@router.callback_query(F.data.startswith("apromo:type:"))
async def promo_new_type(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    dtype = cb.data.split(":")[2]
    if dtype not in ("fixed", "percent"):
        await cb.answer("Invalid", show_alert=True)
        return

    await state.update_data(promo_type=dtype)
    await state.set_state("AdminPromo:value")

    label = "Ks (Fixed)" if dtype == "fixed" else "% (Percent)"

    await edit_or_send(
        cb,
        f"Discount: <b>{label}</b>\n\nValue ရိုက်ပါ:",
        reply_markup=back_panel_kb(),
    )
    await cb.answer()


@router.message(StateFilter("AdminPromo:value"), TextInput())
async def promo_new_value(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    try:
        val = int(
            (message.text or "")
            .strip()
            .replace(",", "")
            .replace("%", "")
        )
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    if val <= 0:
        await message.answer("0 ထက် ကြီး:")
        return

    data = await state.get_data()
    dtype = data.get("promo_type", "fixed")

    if dtype == "percent" and val > 100:
        await message.answer("Percent 100 အောက်:")
        return

    await state.update_data(promo_value=val)
    await state.set_state("AdminPromo:min_purchase")

    unit = "%" if dtype == "percent" else " Ks"
    await message.answer(
        f"Value: {val}{unit}\n\n"
        f"Min purchase (Ks, 0 = မလိုအပ်):"
    )


@router.message(
    StateFilter("AdminPromo:min_purchase"), TextInput()
)
async def promo_new_min(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    try:
        mn = int(
            (message.text or "").strip().replace(",", "")
        )
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    if mn < 0:
        await message.answer(">= 0:")
        return

    await state.update_data(promo_min=mn)
    await state.set_state("AdminPromo:max_uses")

    await message.answer(
        f"Min: {mn:,} Ks\n\n"
        f"Max uses (0 = unlimited):"
    )


@router.message(StateFilter("AdminPromo:max_uses"), TextInput())
async def promo_new_max(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    try:
        mx = int(
            (message.text or "").strip().replace(",", "")
        )
    except ValueError:
        await message.answer("ဂဏန်း:")
        return

    if mx < 0:
        await message.answer(">= 0:")
        return

    await state.update_data(promo_max=mx)
    await state.set_state("AdminPromo:confirm")

    data = await state.get_data()
    dtype = data.get("promo_type", "fixed")
    val = data.get("promo_value", 0)
    label = (
        f"{val}%" if dtype == "percent" else f"{val:,} Ks"
    )

    text = (
        f"<b>PROMO SUMMARY</b>\n\n"
        f"Code: <code>{data['promo_code']}</code>\n"
        f"Discount: {label}\n"
        f"Min: {data['promo_min']:,} Ks\n"
        f"Max uses: {mx if mx else 'Unlimited'}"
    )

    await message.answer(text, reply_markup=promo_confirm_kb())


@router.callback_query(F.data == "apromo:save")
async def promo_save(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    data = await state.get_data()
    if not data.get("promo_code"):
        await cb.answer("Data ပျောက်", show_alert=True)
        return

    try:
        async with SessionLocal() as s:
            p = await create_code(
                s,
                code=data["promo_code"],
                discount_type=data["promo_type"],
                discount_value=data["promo_value"],
                min_purchase=data["promo_min"],
                max_uses=data["promo_max"],
                per_user_limit=1,
            )
            code = p.code
    except ValueError as e:
        await cb.answer(f"{e}", show_alert=True)
        return
    except Exception as e:
        logger.exception(f"Create promo: {e}")
        await cb.answer("Save မရပါ", show_alert=True)
        return

    await state.clear()

    await edit_or_send(
        cb,
        f"<b>Promo ဖန်တီးပြီ</b>\n\n"
        f"<code>{code}</code>",
    )
    await cb.answer("Saved")


@router.callback_query(F.data == "apromo:cancel")
async def promo_cancel(cb: CallbackQuery, state):
    await state.clear()
    try:
        await cb.message.edit_text("Cancelled.")
    except Exception:
        pass
    await cb.answer()
