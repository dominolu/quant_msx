from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class ExchangeAccountRecord(Base):
    __tablename__ = "exchange_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), default="cex", nullable=False)
    exchange: Mapped[str] = mapped_column(String(64), default="MSX", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="unverified", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    credential_fingerprint: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    credential_summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    permissions_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    connection_config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    latest_balance_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latest_equity_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    equity_curve_points_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
