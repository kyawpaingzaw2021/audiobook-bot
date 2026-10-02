"""Purchase service. No commit — caller commits."""
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.book import BookFile
from bot.models.purchase import Purchase
from bot.models.user import User

logger = logging.getLogger(__name__)


async def get_user_by_tg(
    session: AsyncSession, tg_id: int
) -> User | None:
    """Fetch user by Telegram ID."""
    r = await session.execute(
        select(User).where(User.tg_id == tg_id)
    )
    return r.scalar_one_or_none()


async def owns_episode(
    session: AsyncSession,
    user_id: int,
    book_id: int,
    episode_no: int,
) -> bool:
    """Check if user owns an episode."""
    r = await session.execute(
        select(Purchase.id)
        .where(
            Purchase.user_id == user_id,
            Purchase.book_id == book_id,
            Purchase.episode_no == episode_no,
        )
        .limit(1)
    )
    return r.scalar_one_or_none() is not None


async def list_owned_episodes(
    session: AsyncSession, user_id: int, book_id: int
) -> set[int]:
    """Set of owned episode numbers."""
    r = await session.execute(
        select(Purchase.episode_no).where(
            Purchase.user_id == user_id,
            Purchase.book_id == book_id,
        )
    )
    return {row[0] for row in r.all()}


async def get_episode_file(
    session: AsyncSession, book_id: int, episode_no: int
) -> BookFile | None:
    """Fetch episode audio file."""
    r = await session.execute(
        select(BookFile).where(
            BookFile.book_id == book_id,
            BookFile.episode_no == episode_no,
        )
    )
    return r.scalar_one_or_none()


async def list_user_library(
    session: AsyncSession, user_id: int
) -> list[int]:
    """Distinct book_ids user has purchased."""
    r = await session.execute(
        select(Purchase.book_id)
        .where(Purchase.user_id == user_id)
        .distinct()
    )
    return [row[0] for row in r.all()]


async def count_remaining(
    session: AsyncSession, user_id: int, book_id: int
) -> int:
    """Count paid episodes not yet owned."""
    r = await session.execute(
        select(BookFile).where(
            BookFile.book_id == book_id,
            BookFile.is_free == False,  # noqa: E712
        )
    )
    all_paid = list(r.scalars().all())
    owned = await list_owned_episodes(session, user_id, book_id)
    return sum(1 for e in all_paid if e.episode_no not in owned)


async def create_purchase(
    session: AsyncSession,
    user_id: int,
    book_id: int,
    episode_no: int,
    price_paid: int,
    source: str = "single",
) -> Purchase:
    """Create a purchase. Does NOT commit. Raises ValueError on dup."""
    p = Purchase(
        user_id=user_id,
        book_id=book_id,
        episode_no=episode_no,
        price_paid=price_paid,
        source=source,
    )
    session.add(p)

    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("Already purchased") from e

    logger.info(
        f"Purchase: u={user_id} b={book_id} "
        f"ep={episode_no} {price_paid}"
    )
    return p


async def bulk_buy(
    session: AsyncSession,
    user_id: int,
    book_id: int,
    price_per_ep: int = 0,
) -> tuple[int, list[int]]:
    """Create purchases for remaining paid episodes. No commit."""
    r = await session.execute(
        select(BookFile).where(
            BookFile.book_id == book_id,
            BookFile.is_free == False,  # noqa: E712
        )
    )
    all_paid = list(r.scalars().all())
    owned = await list_owned_episodes(session, user_id, book_id)
    remaining = [e for e in all_paid if e.episode_no not in owned]

    if not remaining:
        return 0, []

    nos: list[int] = []
    for e in remaining:
        session.add(Purchase(
            user_id=user_id,
            book_id=book_id,
            episode_no=e.episode_no,
            price_paid=price_per_ep,
            source="bulk",
        ))
        nos.append(e.episode_no)

    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("Some episodes already purchased") from e

    logger.info(f"Bulk: u={user_id} b={book_id} eps={nos}")
    return len(nos), nos


async def delete_user_purchases(
    session: AsyncSession, user_id: int, book_id: int
) -> int:
    """Delete all purchases for a user + book."""
    from sqlalchemy import delete

    r = await session.execute(
        delete(Purchase).where(
            Purchase.user_id == user_id,
            Purchase.book_id == book_id,
        )
    )
    await session.commit()
    return r.rowcount or 0
