"""Admin — user management (search, view, DM, credit, ban)."""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, or_, select

from bot.keyboards.admin_kb import user_view_kb, users_menu_kb
from bot.models.ledger import Ledger
from bot.models.purchase import Purchase
from bot.models.user import User
from bot.services.admin_service import is_admin
from bot.services.db import SessionLocal
from bot.services.wallet import credit, debit
from bot.utils.filters import TextInput
from bot.utils.messaging import edit_or_send

logger = logging.getLogger(__name__)
router = Router(name="admin_users")


async def _ok(cb: CallbackQuery) -> bool:
    async with SessionLocal() as s:
        if not await is_admin(s, cb.from_user.id):
            await cb.answer("Access denied", show_alert=True)
            return False
    return True


async def _build_user_view(user_pk: int) -> dict | None:
    """Build user view data (session-safe dict)."""
    async with SessionLocal() as s:
        u = (
            await s.execute(
                select(User).where(User.id == user_pk)
            )
        ).scalar_one_or_none()

        if u is None:
            return None

        r = await s.execute(
            select(
                func.count(Purchase.id),
                func.coalesce(func.sum(Purchase.price_paid), 0),
            ).where(Purchase.user_id == u.id)
        )
        pc, ts = r.one()

        r = await s.execute(
            select(Ledger)
            .where(Ledger.user_id == u.id)
            .order_by(Ledger.id.desc())
            .limit(3)
        )
        recent = [
            {
                "type": r2.type,
                "amount": r2.amount,
                "balance_after": r2.balance_after,
            }
            for r2 in r.scalars().all()
        ]

        return {
            "id": u.id,
            "tg_id": u.tg_id,
            "username": u.username,
            "first_name": u.first_name,
            "balance": u.balance,
            "is_blocked": u.is_blocked,
            "accepted_terms": u.accepted_terms,
            "created_at": u.created_at,
            "purchases_count": int(pc or 0),
            "total_spent": int(ts or 0),
            "recent": recent,
        }


async def _render(
    target, user_pk: int, *, edit: bool = False
):
    """Render user detail."""
    data = await _build_user_view(user_pk)
    if data is None:
        text = "User မတွေ့ပါ"
        if edit:
            try:
                await target.edit_text(text)
                return
            except Exception:
                pass
        await target.answer(text)
        return

    created = (
        data["created_at"].strftime("%d %b %Y")
        if data["created_at"] else "—"
    )

    text = (
        f"<b>USER</b>\n\n"
        f"ID: {data['tg_id']}\n"
        f"Name: {data['first_name'] or '—'}\n"
        f"Username: @{data['username'] or '—'}\n"
        f"Joined: {created}\n\n"
        f"Balance: {data['balance']:,} Ks\n"
        f"Purchases: {data['purchases_count']}\n"
        f"Total spent: {data['total_spent']:,} Ks\n"
        f"Blocked: {'Yes' if data['is_blocked'] else 'No'}\n"
        f"Terms: {'Yes' if data['accepted_terms'] else 'No'}\n"
    )

    if data["recent"]:
        text += "\nRecent:\n"
        for r in data["recent"]:
            text += (
                f"  {r['type']} {r['amount']:+d} "
                f"-> {r['balance_after']}\n"
            )

    kb = user_view_kb(data["id"], data["is_blocked"])

    if edit:
        try:
            await target.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass

    await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "auser:menu")
async def users_menu(cb: CallbackQuery, state):
    if not await _ok(cb):
        return
    await state.clear()

    await edit_or_send(
        cb,
        "<b>USER MANAGEMENT</b>\n\n"
        "Search by ID, @username, or name:",
        reply_markup=users_menu_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "auser:search")
async def users_search_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    await state.set_state("AdminUser:search")
    await edit_or_send(
        cb,
        "<b>SEARCH USER</b>\n\n"
        "ID, @username, or name ရိုက်ပါ:\n"
        "ဥပမာ: <code>6802169124</code> or <code>@user</code>",
    )
    await cb.answer()


@router.message(StateFilter("AdminUser:search"), TextInput())
async def users_search(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            await state.clear()
            return

    q = (message.text or "").strip()
    await state.clear()

    async with SessionLocal() as s:
        try:
            tg_id = int(q)
            r = await s.execute(
                select(User).where(User.tg_id == tg_id)
            )
            u = r.scalar_one_or_none()
            user_list = [u] if u is not None else []
        except ValueError:
            q2 = q.lstrip("@")
            r = await s.execute(
                select(User)
                .where(
                    or_(
                        User.username.ilike(f"%{q2}%"),
                        User.first_name.ilike(f"%{q2}%"),
                    )
                )
                .limit(5)
            )
            user_list = list(r.scalars().all())

        user_data = [
            {
                "id": u.id,
                "tg_id": u.tg_id,
                "username": u.username,
                "first_name": u.first_name,
            }
            for u in user_list
        ]

    if not user_data:
        await message.answer("User မတွေ့ပါ။")
        return

    if len(user_data) == 1:
        await _render(
            message, user_data[0]["id"], edit=False
        )
    else:
        lines = ["<b>RESULTS</b>", ""]
        for u in user_data:
            uname = f"@{u['username']}" if u["username"] else "—"
            lines.append(
                f"{u['tg_id']} | {uname} | {u['first_name'] or ''}"
            )
        await message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("auser:v:"))
async def user_view_cb(cb: CallbackQuery):
    if not await _ok(cb):
        return

    try:
        user_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer("Invalid", show_alert=True)
        return

    await _render(cb.message, user_id, edit=True)
    await cb.answer()


@router.callback_query(F.data.startswith("auser:dm:"))
async def user_dm_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    user_id = int(cb.data.split(":")[2])
    await state.update_data(target_user_id=user_id)
    await state.set_state("AdminUser:dm_text")

    await edit_or_send(
        cb, "<b>DM ပို့</b>\n\nMessage ရိုက်ပါ:"
    )
    await cb.answer()


@router.message(StateFilter("AdminUser:dm_text"), TextInput())
async def user_dm_send(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    text = (message.text or "").strip()
    if not text or len(text) > 3500:
        await message.answer("1-3500 chars:")
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")
    await state.clear()

    if not user_id:
        await message.answer("Data ပျောက်")
        return

    async with SessionLocal() as s:
        u = (
            await s.execute(
                select(User).where(User.id == user_id)
            )
        ).scalar_one_or_none()
        if u is None:
            await message.answer("User မတွေ့")
            return
        tg_id = u.tg_id

    try:
        await message.bot.send_message(
            chat_id=tg_id,
            text=f"<b>Admin Message</b>\n\n{text[:3500]}",
        )
        await message.answer(f"Sent to {tg_id}")
    except Exception as e:
        await message.answer(f"Send fail: {e}")


@router.callback_query(F.data.startswith("auser:cr:"))
async def user_credit_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    user_id = int(cb.data.split(":")[2])
    await state.update_data(
        target_user_id=user_id, adj_type="credit"
    )
    await state.set_state("AdminUser:adj_amount")

    await edit_or_send(
        cb, "<b>CREDIT</b>\n\nAmount ရိုက်ပါ (Ks):"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("auser:db:"))
async def user_debit_start(cb: CallbackQuery, state):
    if not await _ok(cb):
        return

    user_id = int(cb.data.split(":")[2])
    await state.update_data(
        target_user_id=user_id, adj_type="debit"
    )
    await state.set_state("AdminUser:adj_amount")

    await edit_or_send(
        cb, "<b>DEBIT</b>\n\nAmount ရိုက်ပါ (Ks):"
    )
    await cb.answer()


@router.message(StateFilter("AdminUser:adj_amount"), TextInput())
async def user_adj_amount(message: Message, state):
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

    if amount <= 0:
        await message.answer("0 ထက် ကြီး:")
        return

    data = await state.get_data()
    adj = data.get("adj_type", "credit")
    await state.update_data(adj_amount=amount)
    await state.set_state("AdminUser:adj_reason")

    sign = "+" if adj == "credit" else "-"
    await message.answer(
        f"<b>{sign}{amount:,} Ks</b>\n\n"
        f"Reason ရိုက်ပါ (audit log):"
    )


@router.message(StateFilter("AdminUser:adj_reason"), TextInput())
async def user_adj_reason(message: Message, state):
    async with SessionLocal() as s:
        if not await is_admin(s, message.from_user.id):
            return

    reason = (message.text or "").strip()[:200]
    if not reason:
        await message.answer("Reason ရိုက်ပါ:")
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")
    amount = data.get("adj_amount")
    adj = data.get("adj_type", "credit")
    await state.clear()

    async with SessionLocal() as s:
        u = (
            await s.execute(
                select(User).where(User.id == user_id)
            )
        ).scalar_one_or_none()
        if u is None:
            await message.answer("User မတွေ့")
            return

        tg_id = u.tg_id

        if adj == "credit":
            ok, new_bal, msg = await credit(
                s, tg_id, amount, type_="adjust",
                note=f"Admin +{amount} ({reason})",
            )
        else:
            ok, new_bal, msg = await debit(
                s, tg_id, amount, type_="adjust",
                note=f"Admin -{amount} ({reason})",
            )

        if ok:
            await s.commit()

    if not ok:
        await message.answer(msg)
        return

    sign = "+" if adj == "credit" else "-"

    try:
        await message.bot.send_message(
            chat_id=tg_id,
            text=(
                f"<b>Balance adjusted</b>\n\n"
                f"{sign}{amount:,} Ks\n"
                f"New: {new_bal:,} Ks\n\n"
                f"{reason}"
            ),
        )
    except Exception:
        pass

    await message.answer(
        f"<b>Done</b>\n\n"
        f"User: {tg_id}\n"
        f"Amount: {sign}{amount:,}\n"
        f"Balance: {new_bal:,} Ks"
    )


@router.callback_query(F.data.startswith("auser:ban:"))
async def user_ban(cb: CallbackQuery):
    if not await _ok(cb):
        return

    user_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        u = (
            await s.execute(
                select(User).where(User.id == user_id)
            )
        ).scalar_one_or_none()
        if u is not None:
            u.is_blocked = True
            await s.commit()

    await _render(cb.message, user_id, edit=True)
    await cb.answer("Banned")


@router.callback_query(F.data.startswith("auser:unban:"))
async def user_unban(cb: CallbackQuery):
    if not await _ok(cb):
        return

    user_id = int(cb.data.split(":")[2])

    async with SessionLocal() as s:
        u = (
            await s.execute(
                select(User).where(User.id == user_id)
            )
        ).scalar_one_or_none()
        if u is not None:
            u.is_blocked = False
            await s.commit()

    await _render(cb.message, user_id, edit=True)
    await cb.answer("Unbanned")
