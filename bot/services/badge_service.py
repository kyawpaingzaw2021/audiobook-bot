"""Badge + top spenders service."""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.purchase import Purchase
from bot.models.user import User

logger = logging.getLogger(__name__)


BADGES: list[tuple[int, str]] = [
    (0, "Newcomer"),
    (1000, "Reader"),
    (5000, "Listener"),
    (15000, "Fan"),
    (50000, "Legend"),
]


async def get_user_badge(
    session: AsyncSession, user_id: int
) -> tuple[int, str]:
    """Return (total_spent, badge_label)."""
    r = await session.execute(
        select(func.coalesce(func.sum(Purchase.price_paid), 0))
        .where(Purchase.user_id == user_id)
    )
    total = int(r.scalar() or 0)

    label = BADGES[0][1]
    for threshold, lbl in BADGES:
        if total >= threshold:
            label = lbl
        else:
            break
    return total, label


async def top_spenders(
    session: AsyncSession, limit: int = 10
) -> list[tuple[User, int]]:
    """Top spenders with user objects (single JOIN)."""
    r = await session.execute(
        select(User, func.sum(Purchase.price_paid).label("total"))
        .join(Purchase, Purchase.user_id == User.id)
        .group_by(User.id)
        .order_by(func.sum(Purchase.price_paid).desc())
        .limit(limit)
    )
    return [(u, int(total or 0)) for u, total in r.all()]
