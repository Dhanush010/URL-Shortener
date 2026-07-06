import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import ShortCodeGenerationError
from app.models.url import URL

BASE62_CHARS = string.ascii_letters + string.digits


def generate_short_code(length: int | None = None) -> str:
    """Generate a random base62 short code of the given length."""
    settings = get_settings()
    code_length = length or settings.short_code_length
    return "".join(secrets.choice(BASE62_CHARS) for _ in range(code_length))


async def short_code_exists(session: AsyncSession, short_code: str) -> bool:
    """Return True if the short code already exists in the database."""
    result = await session.execute(
        select(URL.id).where(URL.short_code == short_code).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def generate_unique_short_code(session: AsyncSession) -> str:
    """Generate a collision-safe base62 short code."""
    settings = get_settings()

    for _ in range(settings.short_code_max_retries):
        code = generate_short_code()
        if not await short_code_exists(session, code):
            return code

    raise ShortCodeGenerationError(
        "Unable to generate a unique short code after maximum retries.",
        instance="/api/v1/shorten",
    )
