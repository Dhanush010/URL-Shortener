import hashlib
import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.exceptions import ConflictError, NotFoundError
from app.models.click_event import ClickEvent
from app.models.url import URL
from app.utils.shortcode import generate_unique_short_code, short_code_exists

RECENT_CLICKS_LIMIT = 10
MAX_PAGE_LIMIT = 100


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


def hash_client_ip(client_ip: str) -> str:
    """Hash a client IP address for privacy-preserving analytics."""
    settings = get_settings()
    digest = hashlib.sha256(f"{client_ip}:{settings.secret_key}".encode())
    return digest.hexdigest()


async def log_click_async(
    short_code: str,
    *,
    user_agent: str | None,
    ip_hash: str | None,
) -> None:
    """Record a click event and increment the URL click count (fire-and-forget)."""
    async with async_session_factory() as session:
        try:
            session.add(
                ClickEvent(
                    short_code=short_code,
                    user_agent=user_agent,
                    ip_hash=ip_hash,
                )
            )
            await session.execute(
                update(URL)
                .where(URL.short_code == short_code)
                .values(click_count=URL.click_count + 1)
            )
            await session.commit()
        except Exception:
            await session.rollback()


async def get_url_stats(
    session: AsyncSession,
    short_code: str,
) -> tuple[URL, list[ClickEvent]]:
    """Return URL analytics including recent click events."""
    url_row = await resolve_url(session, short_code)
    if url_row is None:
        raise NotFoundError(
            f"No URL found for short code '{short_code}'.",
            instance=f"/api/v1/links/{short_code}/stats",
        )

    result = await session.execute(
        select(ClickEvent)
        .where(ClickEvent.short_code == short_code)
        .order_by(desc(ClickEvent.clicked_at))
        .limit(RECENT_CLICKS_LIMIT)
    )
    recent_clicks = list(result.scalars().all())
    return url_row, recent_clicks


async def list_urls(
    session: AsyncSession,
    *,
    page: int = 1,
    limit: int = 20,
    sort: str = "created_at",
) -> tuple[list[URL], int, int, int, int]:
    """Return a paginated list of URLs."""
    limit = min(max(limit, 1), MAX_PAGE_LIMIT)
    page = max(page, 1)
    offset = (page - 1) * limit

    total_result = await session.execute(select(func.count()).select_from(URL))
    total = total_result.scalar_one()

    query = select(URL)
    if sort == "created_at":
        query = query.order_by(desc(URL.created_at))
    else:
        query = query.order_by(desc(URL.created_at))

    result = await session.execute(query.offset(offset).limit(limit))
    items = list(result.scalars().all())
    pages = math.ceil(total / limit) if total > 0 else 0

    return items, total, page, limit, pages
