from rest_framework.throttling import ScopedRateThrottle


def client_ip(request) -> str | None:
    """Client address. Behind Nginx the first X-Forwarded-For entry is the browser (Nginx overwrites it)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:400]


class ClientIpScopedThrottle(ScopedRateThrottle):
    """Scoped throttle keyed on `client_ip` (one address), not DRF's default of the whole X-Forwarded-For string,
    which a client could vary to dodge the limit when a proxy appends to the header."""

    def get_ident(self, request):
        return client_ip(request) or ""
