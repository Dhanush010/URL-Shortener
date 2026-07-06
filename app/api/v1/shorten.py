from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.schemas.errors import ProblemDetail
from app.schemas.url import ShortenRequest, ShortenResponse
from app.services.url_service import build_short_url, create_short_url

router = APIRouter()


@router.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a short URL",
    description=(
        "Accepts an HTTP/HTTPS URL and returns a shortened link. "
        "Optionally accepts a custom short code or expiration window."
    ),
    responses={
        422: {
            "model": ProblemDetail,
            "description": "Invalid URL or custom code.",
        },
        409: {
            "model": ProblemDetail,
            "description": "Custom code already in use.",
        },
        429: {
            "model": ProblemDetail,
            "description": "Rate limit exceeded.",
        },
    },
)
async def shorten_url(
    body: ShortenRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ShortenResponse:
    """Create a new short URL mapping."""
    url_row = await create_short_url(
        session,
        original_url=body.url,
        custom_code=body.custom_code,
        expires_in_days=body.expires_in_days,
    )

    return ShortenResponse(
        short_code=url_row.short_code,
        short_url=build_short_url(url_row.short_code),
        original_url=url_row.original_url,
        created_at=url_row.created_at,
        expires_at=url_row.expires_at,
    )
