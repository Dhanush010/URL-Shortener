from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class URL(Base):
    """SQLAlchemy model for shortened URLs."""

    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    click_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        Index("idx_urls_short_code", "short_code", unique=True),
        Index("idx_urls_api_key", "api_key"),
        Index("idx_urls_created_at", created_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<URL(short_code={self.short_code!r})>"
