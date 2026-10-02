"""Book service — CRUD with optional commit for atomicity."""
import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.book import Book, BookFile

logger = logging.getLogger(__name__)


async def list_books(
    session: AsyncSession,
    category_id: int | None = None,
    active_only: bool = True,
    limit: int = 20,
) -> list[Book]:
    """List books, newest first."""
    stmt = (
        select(Book)
        .order_by(Book.created_at.desc())
        .limit(limit)
    )
    if category_id is not None:
        stmt = stmt.where(Book.category_id == category_id)
    if active_only:
        stmt = stmt.where(Book.is_active == True)  # noqa: E712

    r = await session.execute(stmt)
    return list(r.scalars().all())


async def get_book(
    session: AsyncSession, book_id: int
) -> Book | None:
    """Fetch book by ID."""
    r = await session.execute(
        select(Book).where(Book.id == book_id)
    )
    return r.scalar_one_or_none()


async def get_book_with_files(
    session: AsyncSession, book_id: int
) -> Book | None:
    """Fetch book with files eagerly loaded."""
    r = await session.execute(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.files))
    )
    return r.scalar_one_or_none()


async def count_episodes(
    session: AsyncSession, book_id: int
) -> int:
    """Count episodes for a book."""
    r = await session.execute(
        select(func.count(BookFile.id)).where(
            BookFile.book_id == book_id
        )
    )
    return int(r.scalar() or 0)


async def list_episodes(
    session: AsyncSession, book_id: int
) -> list[BookFile]:
    """List episodes ordered by number."""
    r = await session.execute(
        select(BookFile)
        .where(BookFile.book_id == book_id)
        .order_by(BookFile.episode_no)
    )
    return list(r.scalars().all())


async def get_episode(
    session: AsyncSession, book_id: int, episode_no: int
) -> BookFile | None:
    """Fetch single episode."""
    r = await session.execute(
        select(BookFile).where(
            BookFile.book_id == book_id,
            BookFile.episode_no == episode_no,
        )
    )
    return r.scalar_one_or_none()


async def search_books(
    session: AsyncSession, query: str, limit: int = 15
) -> list[Book]:
    """Search by title or author (case-insensitive)."""
    q = f"%{query.strip()}%"
    stmt = (
        select(Book)
        .where(
            Book.is_active == True,  # noqa: E712
            or_(Book.title.ilike(q), Book.author.ilike(q)),
        )
        .order_by(Book.created_at.desc())
        .limit(limit)
    )
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def create_book(
    session: AsyncSession,
    data: dict,
    *,
    commit: bool = True,
) -> Book:
    """Create a book. If commit=False, caller must commit."""
    book = Book(**data)
    session.add(book)

    if commit:
        await session.commit()
        await session.refresh(book)
        logger.info(f"Book created: #{book.id} {book.title}")
    else:
        await session.flush()

    return book


async def add_episode(
    session: AsyncSession,
    book_id: int,
    episode_no: int,
    audio_file_id: str,
    duration: int = 0,
    file_size: int = 0,
    is_free: bool = False,
    storage_msg_id: int | None = None,
    *,
    commit: bool = True,
) -> BookFile:
    """Add an episode. If commit=False, caller must commit."""
    ep = BookFile(
        book_id=book_id,
        episode_no=episode_no,
        audio_file_id=audio_file_id,
        duration=duration,
        file_size=file_size,
        is_free=is_free,
        storage_msg_id=storage_msg_id,
    )
    session.add(ep)

    if commit:
        await session.commit()
        await session.refresh(ep)
        logger.info(
            f"Episode: book={book_id} ep={episode_no} free={is_free}"
        )
    else:
        await session.flush()

    return ep


async def update_book(
    session: AsyncSession,
    book_id: int,
    **fields,
) -> Book | None:
    """Update book fields."""
    book = await get_book(session, book_id)
    if book is None:
        return None

    for key, value in fields.items():
        if hasattr(book, key):
            setattr(book, key, value)

    await session.commit()
    await session.refresh(book)
    return book


async def delete_book_soft(
    session: AsyncSession, book_id: int
) -> bool:
    """Soft delete (is_active=False)."""
    book = await get_book(session, book_id)
    if book is None:
        return False
    book.is_active = False
    await session.commit()
    return True
