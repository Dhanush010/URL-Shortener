from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details response body."""

    type: str = Field(..., examples=["https://errors.url-shortener.dev/invalid-url"])
    title: str = Field(..., examples=["Invalid URL"])
    status: int = Field(..., examples=[422])
    detail: str = Field(
        ...,
        examples=["The provided URL is not a valid HTTP/HTTPS URL."],
    )
    instance: str | None = Field(None, examples=["/api/v1/shorten"])
    retry_after: int | None = Field(
        None,
        examples=[42],
        description="Seconds until the client may retry (rate limit responses only).",
    )
