"""Promo service.

- validate_code: read-only
- redeem: no commit + atomic increment
- create_code: commits (race-safe)
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.promo import PromoCode, PromoRedemption

logger = logging.getLogger(__name__)


async def find_code(
    session: AsyncSession, code: str
) -> PromoCode | None:
    """Lookup promo by code (case-insensitive)."""
    r = await session.execute(
        select(PromoCode).where(
            PromoCode.code == code.upper().strip()
        )
    )
    return r.scalar_one_or_none()


async def validate_code(
    session: AsyncSession,
    code: str,
    user_id: int,
    purchase_amount: int,
) -> tuple[bool, str, int, PromoCode | None]:
    """Validate promo code. Returns (ok, message, discount, promo)."""
    if not code:
        return False, "Promo code အလွတ်", 0, None

    promo = await find_code(session, code)
    if promo is None:
        return False, "Promo code မှားနေပါတယ်", 0, None
    if not promo.is_active:
        return False, "Promo code ပိတ်ထားပါတယ်", 0, promo

    if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
        return False, "Promo code expire ဖြစ်ပါပြီ", 0, promo

    if promo.max_uses > 0 and promo.used_count >= promo.max_uses:
        return False, "Promo code ကုန်သွားပါပြီ", 0, promo

    if purchase_amount < promo.min_purchase:
        return (
            False,
            f"အနည်းဆုံး {promo.min_purchase:,} Ks လိုပါ",
            0,
            promo,
        )

    r = await session.execute(
        select(func.count(PromoRedemption.id)).where(
            PromoRedemption.promo_id == promo.id,
            PromoRedemption.user_id == user_id,
        )
    )
    uses = int(r.scalar() or 0)
    if uses >= promo.per_user_limit:
        return False, "ဒီ code ကို သုံးပြီးသားပါ", 0, promo

    if promo.discount_type == "fixed":
        discount = min(promo.discount_value, purchase_amount)
    else:
        discount = (purchase_amount * promo.discount_value) // 100

    if discount <= 0:
        return False, "ဒီ code က discount မပေးပါ", 0, promo

    return True, "OK", discount, promo


async def redeem(
    session: AsyncSession,
    promo: PromoCode,
    user_id: int,
    discount: int,
    reference: str,
) -> None:
    """Create redemption + atomic increment. Does NOT commit."""
    session.add(PromoRedemption(
        promo_id=promo.id,
        user_id=user_id,
        discount_amount=discount,
        reference=reference,
    ))

    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo.id)
        .values(used_count=PromoCode.used_count + 1)
    )

    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("Promo already redeemed") from e

    logger.info(
        f"Promo redeemed: {promo.code} -{discount} u={user_id}"
    )


async def list_active(
    session: AsyncSession, limit: int = 20
) -> list[PromoCode]:
    """List active promo codes."""
    r = await session.execute(
        select(PromoCode)
        .where(PromoCode.is_active == True)  # noqa: E712
        .order_by(PromoCode.created_at.desc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def list_all(
    session: AsyncSession, limit: int = 30
) -> list[PromoCode]:
    """List all promos (admin view)."""
    r = await session.execute(
        select(PromoCode)
        .order_by(PromoCode.created_at.desc())
        .limit(limit)
    )
    return list(r.scalars().all())


async def create_code(
    session: AsyncSession,
    code: str,
    discount_type: str,
    discount_value: int,
    min_purchase: int = 0,
    max_uses: int = 0,
    per_user_limit: int = 1,
) -> PromoCode:
    """Create promo code. Commits. Raises ValueError on dup."""
    p = PromoCode(
        code=code.upper().strip(),
        discount_type=discount_type,
        discount_value=discount_value,
        min_purchase=min_purchase,
        max_uses=max_uses,
        per_user_limit=per_user_limit,
        is_active=True,
    )
    session.add(p)

    try:
        await session.commit()
        await session.refresh(p)
        logger.info(f"Promo created: {p.code}")
        return p
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("Code ရှိပြီးသား") from e


async def toggle_active(
    session: AsyncSession, promo_id: int
) -> PromoCode | None:
    """Toggle promo active state."""
    r = await session.execute(
        select(PromoCode).where(PromoCode.id == promo_id)
    )
    p = r.scalar_one_or_none()
    if p is None:
        return None

    p.is_active = not p.is_active
    await session.commit()
    await session.refresh(p)
    return p


async def delete_code(
    session: AsyncSession, promo_id: int
) -> bool:
    """Delete promo."""
    from sqlalchemy import delete

    r = await session.execute(
        delete(PromoCode).where(PromoCode.id == promo_id)
    )
    await session.commit()
    return (r.rowcount or 0) > 0
