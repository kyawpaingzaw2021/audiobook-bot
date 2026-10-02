"""Book + BookFile models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base


class Book(Base):
    """Audiobook series."""

    __tablename__ = "books"
    __table_args__ = (
        Index("ix_book_cat_active", "category_id", "is_active"),
        Index("ix_book_active_created", "is_active", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    title: Mapped[str] = mapped_column(String(255), index=True)
    author: Mapped[str] = mapped_column(String(255))
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_file_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    episode_price: Mapped[int] = mapped_column(BigInteger, default=0)
    bulk_price: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), default="ongoing")

    storage_chat_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    storage_topic_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    files: Mapped[list["BookFile"]] = relationship(
        "BookFile",
        back_populates="book",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Book #{self.id} {self.title}>"


class BookFile(Base):
    """Episode audio file."""

    __tablename__ = "book_files"
    __table_args__ = (
        UniqueConstraint(
            "book_id", "episode_no", name="uq_book_ep"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("books.id", ondelete="CASCADE"),
        index=True,
    )
    episode_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    audio_file_id: Mapped[str] = mapped_column(String(255))
    duration: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)

    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_msg_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    book: Mapped[Book] = relationship(
        "Book", back_populates="files", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<BookFile book={self.book_id} ep={self.episode_no}>"
