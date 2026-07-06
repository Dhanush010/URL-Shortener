from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

PROBLEM_BASE_URL = "https://errors.url-shortener.dev"


class AppError(Exception):
    """Base application error mapped to RFC 7807 Problem Details."""

    def __init__(
        self,
        *,
        status: int,
        title: str,
        detail: str,
        type_slug: str,
        instance: str | None = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type_slug = type_slug
        self.instance = instance
        super().__init__(detail)


class InvalidURLError(AppError):
    def __init__(self, detail: str, instance: str | None = None) -> None:
        super().__init__(
            status=422,
            title="Invalid URL",
            detail=detail,
            type_slug="invalid-url",
            instance=instance,
        )


class InvalidCustomCodeError(AppError):
    def __init__(self, detail: str, instance: str | None = None) -> None:
        super().__init__(
            status=422,
            title="Invalid Custom Code",
            detail=detail,
            type_slug="invalid-custom-code",
            instance=instance,
        )


class ConflictError(AppError):
    def __init__(self, detail: str, instance: str | None = None) -> None:
        super().__init__(
            status=409,
            title="Conflict",
            detail=detail,
            type_slug="conflict",
            instance=instance,
        )


class NotFoundError(AppError):
    def __init__(self, detail: str, instance: str | None = None) -> None:
        super().__init__(
            status=404,
            title="Not Found",
            detail=detail,
            type_slug="not-found",
            instance=instance,
        )


class GoneError(AppError):
    def __init__(self, detail: str, instance: str | None = None) -> None:
        super().__init__(
            status=410,
            title="Gone",
            detail=detail,
            type_slug="gone",
            instance=instance,
        )


class ShortCodeGenerationError(AppError):
    def __init__(self, detail: str, instance: str | None = None) -> None:
        super().__init__(
            status=500,
            title="Short Code Generation Failed",
            detail=detail,
            type_slug="short-code-generation-failed",
            instance=instance,
        )


class RateLimitExceededError(AppError):
    def __init__(self, *, retry_after: int, instance: str | None = None) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.retry_after = retry_after
        super().__init__(
            status=429,
            title="Too Many Requests",
            detail=(
                f"Rate limit exceeded. Max {settings.rate_limit_requests} "
                f"requests per minute per IP."
            ),
            type_slug="rate-limited",
            instance=instance,
        )


def _problem_response(
    *,
    status: int,
    title: str,
    detail: str,
    type_slug: str,
    instance: str | None,
    extra: dict | None = None,
    headers: dict | None = None,
) -> JSONResponse:
    content = {
        "type": f"{PROBLEM_BASE_URL}/{type_slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
    }
    if extra:
        content.update(extra)
    return JSONResponse(
        status_code=status,
        content=content,
        media_type="application/problem+json",
        headers=headers,
    )


def rate_limit_exceeded_response(retry_after: int, instance: str) -> JSONResponse:
    """Build an RFC 7807 response for rate limit violations."""
    from app.config import get_settings

    settings = get_settings()
    return _problem_response(
        status=429,
        title="Too Many Requests",
        detail=(
            f"Rate limit exceeded. Max {settings.rate_limit_requests} "
            f"requests per minute per IP."
        ),
        type_slug="rate-limited",
        instance=instance,
        extra={"retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register RFC 7807 exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        extra: dict | None = None
        headers: dict | None = None

        if isinstance(exc, RateLimitExceededError):
            extra = {"retry_after": exc.retry_after}
            headers = {"Retry-After": str(exc.retry_after)}

        return _problem_response(
            status=exc.status,
            title=exc.title,
            detail=exc.detail,
            type_slug=exc.type_slug,
            instance=exc.instance or str(request.url.path),
            extra=extra,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        detail = "The request body is invalid."
        type_slug = "validation-error"
        title = "Validation Error"

        if exc.errors():
            first = exc.errors()[0]
            msg = first.get("msg", detail)
            if msg.startswith("Value error, "):
                msg = msg.removeprefix("Value error, ")
            detail = msg

            loc = first.get("loc", ())
            field = loc[-1] if loc else None
            if field == "url":
                type_slug = "invalid-url"
                title = "Invalid URL"
            elif field == "custom_code":
                type_slug = "invalid-custom-code"
                title = "Invalid Custom Code"

        return _problem_response(
            status=422,
            title=title,
            detail=detail,
            type_slug=type_slug,
            instance=str(request.url.path),
        )
