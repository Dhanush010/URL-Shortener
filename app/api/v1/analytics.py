from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.schemas.errors import ProblemDetail
from app.schemas.url import (
    PaginatedURLResponse,
    RecentClick,
    URLListItem,
    URLStatsResponse,
)
from app.services.url_service import build_short_url, get_url_stats, list_urls

router = APIRouter(prefix="/links", tags=["analytics"])


@router.get(
    "",
    response_model=PaginatedURLResponse,
    summary="List shortened URLs",
    description="Return a paginated list of all shortened URLs.",
    responses={
        200: {"description": "Paginated URL list."},
    },
)
async def list_short_urls(
    page: int = Query(1, ge=1, description="Page number (1-based)."),
    limit: int = Query(20, ge=1, le=100, description="Items per page."),
    sort: str = Query("created_at", description="Sort field (currently: created_at)."),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedURLResponse:
    """List all shortened URLs with pagination."""
    items, total, page, limit, pages = await list_urls(
        session,
        page=page,
        limit=limit,
        sort=sort,
    )

    return PaginatedURLResponse(
        items=[
            URLListItem(
                short_code=row.short_code,
                short_url=build_short_url(row.short_code),
                original_url=row.original_url,
                click_count=row.click_count,
                created_at=row.created_at,
                expires_at=row.expires_at,
                is_active=row.is_active,
            )
            for row in items
        ],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get(
    "/{code}/stats",
    response_model=URLStatsResponse,
    summary="Get URL analytics",
    description=(
        "Return click count and recent click events for a short URL."
    ),
    responses={
        200: {"description": "Analytics for the short URL."},
        404: {"model": ProblemDetail, "description": "Short code not found."},
    },
)
async def get_link_stats(
    code: str,
    session: AsyncSession = Depends(get_db_session),
) -> URLStatsResponse:
    """Get analytics stats for a short URL."""
    url_row, recent_clicks = await get_url_stats(session, code)

    return URLStatsResponse(
        short_code=url_row.short_code,
        original_url=url_row.original_url,
        click_count=url_row.click_count,
        created_at=url_row.created_at,
        expires_at=url_row.expires_at,
        recent_clicks=[
            RecentClick(clicked_at=click.clicked_at, user_agent=click.user_agent)
            for click in recent_clicks
        ],
    )
