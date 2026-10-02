"""Purchase model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Purchase(Base):
    """Episode purchase record."""

    __tablename__ = "purchases"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "book_id", "episode_no",
            name="uq_user_book_ep",
        ),
        Index("ix_purchase_user_book", "user_id", "book_id"),
        Index("ix_purchase_book_time", "book_id", "purchased_at"),
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
    episode_no: Mapped[int] = mapped_column(BigInteger)

    price_paid: Mapped[int] = mapped_column(BigInteger, default=0)
    source: Mapped[str] = mapped_column(String(20), default="single")

    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Purchase u={self.user_id} b={self.book_id} "
            f"ep={self.episode_no}>"
        )
