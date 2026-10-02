"""BookRequest model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class BookRequest(Base):
    """User-requested book."""

    __tablename__ = "book_requests"
    __table_args__ = (
        Index("ix_req_status_created", "status", "created_at"),
        Index(
            "uq_req_user_pending_title",
            "user_id",
            func.lower(text("title")),
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )

    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    admin_note: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    book_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("books.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<BookRequest #{self.id} {self.title} ({self.status})>"
        )
