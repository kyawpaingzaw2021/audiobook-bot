"""TopupRequest model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class TopupRequest(Base):
    """Manual topup request (screenshot verified by admin)."""

    __tablename__ = "topup_requests"
    __table_args__ = (
        Index("ix_topup_status_created", "status", "created_at"),
        Index("ix_topup_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )

    amount: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(20))
    account_number: Mapped[str] = mapped_column(String(50))

    screenshot_file_id: Mapped[str] = mapped_column(String(500))
    file_unique_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )

    reject_reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    adjusted_amount: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
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
        return f"<Topup #{self.id} {self.amount} {self.status}>"
