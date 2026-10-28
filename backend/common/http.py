from rest_framework.throttling import ScopedRateThrottle

from .stores import SecurityStoreUnavailable, security_store


def client_ip(request) -> str | None:
    """Client address. Behind Nginx the first X-Forwarded-For entry is the browser (Nginx overwrites it)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:400]


class SecurityStoreThrottle:
    """Mixin: throttle history in the security store (never evicted), and a store error refuses the request (503)."""

    @property
    def cache(self):
        return security_store()

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except SecurityStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed
            raise SecurityStoreUnavailable() from exc


class ClientIpScopedThrottle(SecurityStoreThrottle, ScopedRateThrottle):
    """Scoped throttle keyed on `client_ip` (one address), not DRF's default of the whole X-Forwarded-For string,
    which a client could vary to dodge the limit when a proxy appends to the header. History lives in the security
    store, so memory pressure cannot evict it and reset the limit."""

    def get_ident(self, request):
        return client_ip(request) or ""
