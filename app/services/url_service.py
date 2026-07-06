from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import ConflictError
from app.models.url import URL
from app.utils.shortcode import generate_unique_short_code, short_code_exists


async def create_short_url(
    session: AsyncSession,
    *,
    original_url: str,
    custom_code: str | None = None,
    expires_in_days: int | None = None,
) -> URL:
    """Create and persist a new shortened URL."""
    if custom_code:
        if await short_code_exists(session, custom_code):
            raise ConflictError(
                f"The custom code '{custom_code}' is already in use.",
                instance="/api/v1/shorten",
            )
        short_code = custom_code
    else:
        short_code = await generate_unique_short_code(session)

    expires_at: datetime | None = None
    if expires_in_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

    url_row = URL(
        short_code=short_code,
        original_url=original_url,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(url_row)
    await session.flush()
    await session.refresh(url_row)
    return url_row


async def resolve_url(session: AsyncSession, short_code: str) -> URL | None:
    """Look up a URL row by short code."""
    result = await session.execute(
        select(URL).where(URL.short_code == short_code).limit(1)
    )
    return result.scalar_one_or_none()


def is_url_expired(url_row: URL, *, now: datetime | None = None) -> bool:
    """Return True if the URL has passed its expiration time."""
    if url_row.expires_at is None:
        return False
    current = now or datetime.now(UTC)
    expires_at = url_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return current >= expires_at


def build_short_url(short_code: str) -> str:
    """Build the full short URL from a short code."""
    settings = get_settings()
    base = settings.base_url.rstrip("/")
    return f"{base}/{short_code}"
