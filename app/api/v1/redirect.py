from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import RedirectResponse

from app.database import async_session_factory
from app.exceptions import GoneError, NotFoundError
from app.schemas.errors import ProblemDetail
from app.services import cache_service
from app.services.cache_service import CachedExpired
from app.services.rate_limiter import get_client_ip
from app.services.url_service import (
    hash_client_ip,
    is_url_expired,
    log_click_async,
    resolve_url,
)

router = APIRouter()


def _schedule_click_log(
    background_tasks: BackgroundTasks,
    request: Request,
    short_code: str,
) -> None:
    """Fire-and-forget click logging for a successful redirect."""
    background_tasks.add_task(
        log_click_async,
        short_code,
        user_agent=request.headers.get("user-agent"),
        ip_hash=hash_client_ip(get_client_ip(request)),
    )


@router.get(
    "/{code}",
    summary="Redirect to original URL",
    description=(
        "Resolves a short code and redirects to the original URL with HTTP 301. "
        "Uses Redis cache-aside for hot lookups. Returns 404 if the code does not "
        "exist, or 410 if expired or deactivated. Click events are logged "
        "asynchronously."
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
    request: Request,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    """Redirect a short code to its original URL."""
    cached = await cache_service.get(code)

    if cached is not None:
        if isinstance(cached, CachedExpired) or not cached.is_active:
            raise GoneError(
                f"The short URL '{code}' has expired or been deactivated.",
                instance=f"/{code}",
            )
        _schedule_click_log(background_tasks, request, code)
        response = RedirectResponse(url=cached.original_url, status_code=301)
        response.headers["X-Cache"] = "HIT"
        return response

    async with async_session_factory() as session:
        url_row = await resolve_url(session, code)

        if url_row is None:
            raise NotFoundError(
                f"No URL found for short code '{code}'.",
                instance=f"/{code}",
            )

        if not url_row.is_active or is_url_expired(url_row):
            await cache_service.set_negative(code)
            raise GoneError(
                f"The short URL '{code}' has expired or been deactivated.",
                instance=f"/{code}",
            )

        await cache_service.set(
            code,
            original_url=url_row.original_url,
            is_active=url_row.is_active,
        )

    _schedule_click_log(background_tasks, request, code)
    response = RedirectResponse(url=url_row.original_url, status_code=301)
    response.headers["X-Cache"] = "MISS"
    return response
