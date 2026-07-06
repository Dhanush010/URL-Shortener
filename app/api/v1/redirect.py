from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.exceptions import GoneError, NotFoundError
from app.schemas.errors import ProblemDetail
from app.services.url_service import is_url_expired, resolve_url

router = APIRouter()


@router.get(
    "/{code}",
    summary="Redirect to original URL",
    description=(
        "Resolves a short code and redirects to the original URL with HTTP 301. "
        "Returns 404 if the code does not exist, or 410 if expired or deactivated."
    ),
    response_class=RedirectResponse,
    responses={
        301: {"description": "Permanent redirect to the original URL."},
        404: {"model": ProblemDetail, "description": "Short code not found."},
        410: {"model": ProblemDetail, "description": "URL expired or deactivated."},
    },
)
async def redirect_to_url(
    code: str,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    """Redirect a short code to its original URL."""
    url_row = await resolve_url(session, code)

    if url_row is None:
        raise NotFoundError(
            f"No URL found for short code '{code}'.",
            instance=f"/{code}",
        )

    if not url_row.is_active or is_url_expired(url_row):
        raise GoneError(
            f"The short URL '{code}' has expired or been deactivated.",
            instance=f"/{code}",
        )

    return RedirectResponse(url=url_row.original_url, status_code=301)
