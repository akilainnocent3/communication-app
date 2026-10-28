"""One error shape everywhere: {"code", "detail", "errors"}."""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

FRIENDLY = {
    "not_authenticated": "Your session has ended. Sign in again.",
    "authentication_failed": "Your session has ended. Sign in again.",
    "permission_denied": "You don't have permission to do this.",
    "not_found": "This item was not found. It may have been deleted.",
    "throttled": "Too many attempts. Please wait a moment and try again.",
    "method_not_allowed": "This action is not allowed here.",
    "parse_error": "The request could not be read.",
    "unsupported_media_type": "This file or request type is not supported.",
}


class ApiError(exceptions.APIException):
    """Business error with a stable machine code and a friendly message."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "error"

    def __init__(self, code: str, detail: str, status_code: int | None = None, errors: dict | None = None):
        self.code = code
        self.errors = errors or {}
        if status_code:
            self.status_code = status_code
        super().__init__(detail=detail, code=code)


def _flatten(detail):
    if isinstance(detail, dict):
        return {key: _flatten(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [str(item) if not isinstance(item, (dict, list)) else _flatten(item) for item in detail]
    return str(detail)


def exception_handler(exc, context):
    from .stores import SecurityStoreUnavailable

    if isinstance(exc, SecurityStoreUnavailable):
        # Fail closed: a control that cannot be checked refuses the request (common/stores.py).
        return Response({"code": "try_later", "detail": "This is temporarily unavailable. Try again in a minute.", "errors": {}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, ApiError):
        return Response({"code": exc.code, "detail": str(exc.detail), "errors": exc.errors}, status=exc.status_code)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, exceptions.ValidationError):
        errors = _flatten(exc.detail)
        if isinstance(errors, list):
            errors = {"non_field_errors": errors}
        first = next(iter(errors.values()), None) if errors else None
        detail = "Please check the highlighted fields."
        if isinstance(errors, dict) and list(errors) == ["non_field_errors"] and first:
            detail = first[0] if isinstance(first, list) else str(first)
        response.data = {"code": "validation_error", "detail": detail, "errors": errors}
        return response

    code = getattr(exc, "default_code", "error")
    codes = exc.get_codes() if hasattr(exc, "get_codes") else code
    if isinstance(codes, str):
        code = codes
    detail = FRIENDLY.get(code) or str(getattr(exc, "detail", "Something went wrong."))
    if isinstance(exc, exceptions.Throttled) and exc.wait:
        detail = f"Too many attempts. Try again in {int(exc.wait) + 1} seconds."
    response.data = {"code": code, "detail": detail, "errors": {}}
    return response
