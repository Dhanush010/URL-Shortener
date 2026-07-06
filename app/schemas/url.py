import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

CUSTOM_CODE_PATTERN = re.compile(r"^[a-zA-Z0-9-]{3,10}$")


class ShortenRequest(BaseModel):
    """Request body for creating a short URL."""

    url: str = Field(
        ...,
        examples=["https://www.example.com/very/long/url"],
        description="The original HTTP or HTTPS URL to shorten.",
    )
    custom_code: str | None = Field(
        None,
        examples=["mylink"],
        description="Optional custom short code (3-10 alphanumeric characters or hyphens).",
    )
    expires_in_days: int | None = Field(
        None,
        ge=1,
        examples=[30],
        description="Optional number of days until the short URL expires.",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("The provided URL is not a valid HTTP/HTTPS URL.")
        return value

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not CUSTOM_CODE_PATTERN.match(value):
            raise ValueError(
                "Custom code must be 3-10 characters and contain only "
                "letters, numbers, and hyphens."
            )
        return value


class ShortenResponse(BaseModel):
    """Response body after successfully creating a short URL."""

    model_config = ConfigDict(from_attributes=True)

    short_code: str = Field(..., examples=["abc123"])
    short_url: str = Field(..., examples=["http://localhost:8000/abc123"])
    original_url: str = Field(..., examples=["https://www.example.com/very/long/url"])
    created_at: datetime = Field(..., examples=["2026-07-06T10:00:00Z"])
    expires_at: datetime | None = Field(None, examples=["2026-08-05T10:00:00Z"])


class RecentClick(BaseModel):
    """A single recent click event."""

    model_config = ConfigDict(from_attributes=True)

    clicked_at: datetime = Field(..., examples=["2026-07-06T12:30:00Z"])
    user_agent: str | None = Field(None, examples=["Mozilla/5.0"])


class URLStatsResponse(BaseModel):
    """Analytics response for a short URL."""

    short_code: str = Field(..., examples=["abc123"])
    original_url: str = Field(..., examples=["https://example.com"])
    click_count: int = Field(..., examples=[1423])
    created_at: datetime = Field(..., examples=["2026-07-06T10:00:00Z"])
    expires_at: datetime | None = Field(None, examples=[None])
    recent_clicks: list[RecentClick] = Field(default_factory=list)


class URLListItem(BaseModel):
    """A single URL entry in a paginated list."""

    model_config = ConfigDict(from_attributes=True)

    short_code: str
    short_url: str
    original_url: str
    click_count: int
    created_at: datetime
    expires_at: datetime | None
    is_active: bool


class PaginatedURLResponse(BaseModel):
    """Paginated list of shortened URLs."""

    items: list[URLListItem]
    total: int = Field(..., examples=[150])
    page: int = Field(..., examples=[1])
    limit: int = Field(..., examples=[20])
    pages: int = Field(..., examples=[8])
