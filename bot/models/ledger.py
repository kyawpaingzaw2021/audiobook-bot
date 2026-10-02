"""Ledger model — balance change history."""
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


class Ledger(Base):
    """Balance transaction log."""

    __tablename__ = "ledger"
    __table_args__ = (
        Index("ix_ledger_user_created", "user_id", "created_at"),
        Index("ix_ledger_type_created", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )

    type: Mapped[str] = mapped_column(String(20), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)

    reference_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    note: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<Ledger u={self.user_id} {self.type} {self.amount:+d}>"
