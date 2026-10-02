"""Daily check-in service.

do_checkin() does NOT commit — caller commits.
Uses Asia/Yangon timezone.
"""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.checkin import DailyCheckin
from bot.models.ledger import Ledger
from bot.models.user import User

logger = logging.getLogger(__name__)

MM_TZ = ZoneInfo("Asia/Yangon")

STREAK_BONUSES: dict[int, int] = {
    7: 20,
    30: 100,
}


def today_mm() -> date:
    """Today's date in Myanmar timezone."""
    return datetime.now(MM_TZ).date()


def tomorrow_mm_reset() -> datetime:
    """Next midnight in MM tz (timezone-aware)."""
    now_mm = datetime.now(MM_TZ)
    tomorrow = (now_mm + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return tomorrow


async def get_last_checkin(
    session: AsyncSession, user_id: int
) -> DailyCheckin | None:
    """Most recent check-in for user."""
    r = await session.execute(
        select(DailyCheckin)
        .where(DailyCheckin.user_id == user_id)
        .order_by(DailyCheckin.checkin_date.desc())
        .limit(1)
    )
    return r.scalar_one_or_none()


async def has_checked_in_today(
    session: AsyncSession, user_id: int
) -> bool:
    """Check if user already checked in today (MM time)."""
    r = await session.execute(
        select(DailyCheckin.id)
        .where(
            DailyCheckin.user_id == user_id,
            DailyCheckin.checkin_date == today_mm(),
        )
        .limit(1)
    )
    return r.scalar_one_or_none() is not None


async def do_checkin(
    session: AsyncSession,
    tg_id: int,
    base_reward: int,
) -> tuple[bool, str, int, int, int]:
    """
    Perform daily check-in with streak. Does NOT commit.
    Returns: (success, message, new_balance, streak, total_reward)
    """
    r = await session.execute(
        select(User)
        .where(User.tg_id == tg_id)
        .with_for_update()
    )
    user = r.scalar_one_or_none()

    if user is None:
        return False, "User မတွေ့ပါ", 0, 0, 0
    if user.is_blocked:
        return False, "Account ပိတ်ထားပါသည်", user.balance, 0, 0

    today = today_mm()

    if await has_checked_in_today(session, user.id):
        return False, "ဒီနေ့ စစ်ပြီးသား", user.balance, 0, 0

    last = await get_last_checkin(session, user.id)
    yesterday = today - timedelta(days=1)

    if last is not None and last.checkin_date == yesterday:
        streak = last.streak_count + 1
    else:
        streak = 1

    base = max(0, int(base_reward))
    bonus = STREAK_BONUSES.get(streak, 0)
    total_reward = base + bonus

    new_balance = user.balance + total_reward
    user.balance = new_balance

    session.add(DailyCheckin(
        user_id=user.id,
        checkin_date=today,
        reward=total_reward,
        streak_count=streak,
    ))

    note = f"Daily #{streak}"
    if bonus:
        note += f" +{bonus} bonus"

    session.add(Ledger(
        user_id=user.id,
        type="checkin",
        amount=total_reward,
        balance_after=new_balance,
        note=note,
    ))

    await session.flush()

    msg = f"streak_bonus:{bonus}" if bonus else "OK"

    logger.info(
        f"Checkin u={user.id} streak={streak} "
        f"reward={total_reward} bal={new_balance}"
    )
    return True, msg, new_balance, streak, total_reward


async def count_today(session: AsyncSession) -> int:
    """Count today's check-ins."""
    r = await session.execute(
        select(func.count(DailyCheckin.id)).where(
            DailyCheckin.checkin_date == today_mm()
        )
    )
    return int(r.scalar() or 0)
