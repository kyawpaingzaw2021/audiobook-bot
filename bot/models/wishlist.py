"""Wishlist model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Wishlist(Base):
    """User wishlist entry."""

    __tablename__ = "wishlists"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "book_id", name="uq_user_book_wish"
        ),
        Index("ix_wishlist_user_created", "user_id", "created_at"),
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Wishlist u={self.user_id} b={self.book_id}>"
