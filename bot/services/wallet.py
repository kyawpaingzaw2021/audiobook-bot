"""Wallet operations.

All functions do NOT commit — caller must commit for atomicity.
Uses SELECT FOR UPDATE with deadlock retry.
"""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.ledger import Ledger
from bot.models.user import User

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 0.1


async def get_balance(session: AsyncSession, tg_id: int) -> int:
    """Read balance without lock."""
    r = await session.execute(
        select(User).where(User.tg_id == tg_id)
    )
    user = r.scalar_one_or_none()
    return user.balance if user else 0


async def _locked_user(
    session: AsyncSession, tg_id: int
) -> User | None:
    """Fetch user with row lock + deadlock retry."""
    for attempt in range(MAX_RETRIES):
        try:
            r = await session.execute(
                select(User)
                .where(User.tg_id == tg_id)
                .with_for_update()
            )
            return r.scalar_one_or_none()
        except OperationalError as e:
            err = str(e).lower()
            if "deadlock" in err and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise
    return None


async def adjust_balance(
    session: AsyncSession,
    tg_id: int,
    amount: int,
    type_: str,
    reference_id: int | None = None,
    note: str | None = None,
) -> tuple[bool, int, str]:
    """
    Adjust balance with row lock. Does NOT commit.
    Returns: (success, new_balance, message)
    """
    user = await _locked_user(session, tg_id)

    if user is None:
        return False, 0, "User မတွေ့ပါ"
    if user.is_blocked:
        return False, user.balance, "Account ပိတ်ထားပါသည်"

    new_balance = user.balance + amount
    if new_balance < 0:
        return False, user.balance, "Balance မလုံလောက်ပါ"

    user.balance = new_balance

    session.add(Ledger(
        user_id=user.id,
        type=type_,
        amount=amount,
        balance_after=new_balance,
        reference_id=reference_id,
        note=note,
    ))

    logger.info(
        f"Wallet {tg_id}: {amount:+d} -> {new_balance} ({type_})"
    )
    return True, new_balance, "OK"


async def credit(
    session: AsyncSession,
    tg_id: int,
    amount: int,
    type_: str = "adjust",
    reference_id: int | None = None,
    note: str | None = None,
) -> tuple[bool, int, str]:
    """Positive adjustment. Does NOT commit."""
    return await adjust_balance(
        session, tg_id, abs(amount), type_, reference_id, note
    )


async def debit(
    session: AsyncSession,
    tg_id: int,
    amount: int,
    type_: str = "purchase",
    reference_id: int | None = None,
    note: str | None = None,
) -> tuple[bool, int, str]:
    """Negative adjustment. Does NOT commit."""
    return await adjust_balance(
        session, tg_id, -abs(amount), type_, reference_id, note
    )
