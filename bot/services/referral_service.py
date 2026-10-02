"""Referral service."""
import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.ledger import Ledger
from bot.models.referral import Referral
from bot.models.user import User
from bot.models.user_code import UserCode

logger = logging.getLogger(__name__)


def _gen_code(tg_id: int) -> str:
    """Generate a short referral code."""
    suffix = secrets.token_hex(2).upper()
    return f"R{tg_id % 10000:04d}{suffix}"


async def get_or_create_code(
    session: AsyncSession, user_id: int, tg_id: int
) -> str:
    """Get or create user's referral code. Race-safe."""
    r = await session.execute(
        select(UserCode).where(UserCode.user_id == user_id)
    )
    row = r.scalar_one_or_none()
    if row is not None:
        return row.code

    for _ in range(5):
        code = _gen_code(tg_id)
        r = await session.execute(
            select(UserCode.code).where(UserCode.code == code)
        )
        if r.scalar_one_or_none() is not None:
            continue

        session.add(UserCode(user_id=user_id, code=code))
        try:
            await session.commit()
            return code
        except IntegrityError:
            await session.rollback()
            r = await session.execute(
                select(UserCode).where(
                    UserCode.user_id == user_id
                )
            )
            row = r.scalar_one_or_none()
            if row is not None:
                return row.code
            continue

    raise RuntimeError("Could not generate unique referral code")


async def find_referrer_by_code(
    session: AsyncSession, code: str
) -> User | None:
    """Find the user who owns a referral code."""
    r = await session.execute(
        select(UserCode).where(
            UserCode.code == code.upper().strip()
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        return None

    r = await session.execute(
        select(User).where(User.id == row.user_id)
    )
    return r.scalar_one_or_none()


async def register_referral(
    session: AsyncSession,
    referrer_id: int,
    referred_id: int,
    code: str,
) -> Referral | None:
    """Register a referral. Idempotent + race-safe."""
    if referrer_id == referred_id:
        return None

    r = await session.execute(
        select(Referral.id).where(
            Referral.referred_id == referred_id
        )
    )
    if r.scalar_one_or_none() is not None:
        return None

    ref = Referral(
        referrer_id=referrer_id,
        referred_id=referred_id,
        ref_code=code,
    )
    session.add(ref)

    try:
        await session.commit()
        await session.refresh(ref)
        logger.info(
            f"Referral: {code} ({referrer_id} -> {referred_id})"
        )
        return ref
    except IntegrityError:
        await session.rollback()
        return None


async def pay_referral_bonus(
    session: AsyncSession,
    referred_tg_id: int,
    amount: int,
) -> bool:
    """Pay bonus to referrer on first purchase. Atomic commit."""
    if amount <= 0:
        return False

    r = await session.execute(
        select(User).where(User.tg_id == referred_tg_id)
    )
    referred = r.scalar_one_or_none()
    if referred is None:
        return False

    r = await session.execute(
        select(Referral).where(
            Referral.referred_id == referred.id,
            Referral.bonus_paid == False,  # noqa: E712
        )
    )
    ref = r.scalar_one_or_none()
    if ref is None:
        return False

    r = await session.execute(
        select(User)
        .where(User.id == ref.referrer_id)
        .with_for_update()
    )
    referrer = r.scalar_one_or_none()

    if referrer is None or referrer.is_blocked:
        return False

    new_bal = referrer.balance + amount
    referrer.balance = new_bal

    session.add(Ledger(
        user_id=referrer.id,
        type="adjust",
        amount=amount,
        balance_after=new_bal,
        note=f"Referral bonus (from u={referred.id})",
    ))

    ref.bonus_paid = True
    ref.bonus_amount = amount
    ref.paid_at = datetime.now(timezone.utc)

    await session.commit()

    logger.info(
        f"Referral bonus: +{amount} to {referrer.tg_id} "
        f"(from {referred.tg_id})"
    )
    return True


async def count_referrals(
    session: AsyncSession, user_id: int
) -> int:
    """Total users referred by this user."""
    r = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id
        )
    )
    return int(r.scalar() or 0)


async def count_paid(
    session: AsyncSession, user_id: int
) -> int:
    """Users who paid -> bonus paid."""
    r = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id,
            Referral.bonus_paid == True,  # noqa: E712
        )
    )
    return int(r.scalar() or 0)


async def top_referrers(
    session: AsyncSession, limit: int = 10
) -> list[tuple[int, int]]:
    """Top referrers by bonus paid count."""
    r = await session.execute(
        select(
            Referral.referrer_id,
            func.count(Referral.id).label("cnt"),
        )
        .where(Referral.bonus_paid == True)  # noqa: E712
        .group_by(Referral.referrer_id)
        .order_by(func.count(Referral.id).desc())
        .limit(limit)
    )
    return [(int(uid), int(cnt)) for uid, cnt in r.all()]
