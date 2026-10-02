"""User service — fetch, create, update."""
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User

logger = logging.getLogger(__name__)


async def get_user(
    session: AsyncSession, tg_id: int
) -> User | None:
    """Fetch user by Telegram ID."""
    r = await session.execute(
        select(User).where(User.tg_id == tg_id)
    )
    return r.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession, tg_user
) -> User:
    """Fetch or create user. Handles race on create."""
    user = await get_user(session, tg_user.id)

    if user is not None:
        changed = False
        if user.username != tg_user.username:
            user.username = tg_user.username
            changed = True
        if user.first_name != tg_user.first_name:
            user.first_name = tg_user.first_name
            changed = True
        if changed:
            await session.commit()
            await session.refresh(user)
        return user

    user = User(
        tg_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
    )
    session.add(user)

    try:
        await session.commit()
        await session.refresh(user)
        logger.info(f"New user: tg_id={user.tg_id}")
        return user
    except IntegrityError:
        await session.rollback()
        user = await get_user(session, tg_user.id)
        if user is None:
            raise
        return user


async def accept_terms(
    session: AsyncSession, tg_id: int
) -> User | None:
    """Mark terms as accepted (idempotent)."""
    user = await get_user(session, tg_id)
    if user is None:
        return None

    if not user.accepted_terms:
        user.accepted_terms = True
        await session.commit()
        await session.refresh(user)
        logger.info(f"Terms accepted: tg_id={tg_id}")

    return user
