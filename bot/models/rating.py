"""Rating model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Rating(Base):
    """User rating for a book."""

    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "book_id", name="uq_user_book_rating"
        ),
        CheckConstraint(
            "stars >= 1 AND stars <= 5", name="ck_rating_stars"
        ),
        Index("ix_rating_book_updated", "book_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id"), index=True
    )

    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Rating u={self.user_id} b={self.book_id} {self.stars}*>"
