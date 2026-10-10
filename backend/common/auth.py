from rest_framework.authentication import SessionAuthentication


class CsrfSessionAuthentication(SessionAuthentication):
    """Django session auth; unsafe methods require the CSRF token (sent by the frontend as X-CSRFToken)."""

    def authenticate_header(self, request):
        # A non-empty header makes DRF answer 401 (not 403) when the session is missing or expired.
        return "Session"


def enforce_csrf(request) -> None:
    """CSRF check for endpoints used before login (DRF only checks authenticated sessions)."""
    CsrfSessionAuthentication().enforce_csrf(request)
