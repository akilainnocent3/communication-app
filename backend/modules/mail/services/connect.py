"""Connecting mailboxes: provider detection, connect invites and the Google OAuth web flow (PKCE).

OAuth flow
1. `oauth_url(...)` builds Google's consent URL: PKCE S256, access_type=offline, prompt=consent (guarantees a
   refresh token), include_granted_scopes, login_hint=<expected email>. `state` is a signed, short-lived
   payload (mailbox, invite, nonce, the PKCE verifier encrypted) so the callback needs no server session.
2. `complete_oauth(code, state)` verifies the state, exchanges the code, checks the signed-in account equals
   the expected mailbox and that every required scope was granted, then stores the refresh token encrypted.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone

from common.crypto import encrypt_json, fernet
from modules.audit.services import record

from ..models import Mailbox, MailboxInvite, MailboxStatus, WorkspaceDomain

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
STATE_SALT = "mail.oauth.state"
STATE_MAX_AGE = 15 * 60
GOOGLE_MX = (".google.com", ".googlemail.com", ".google.com.", ".googlemail.com.")
MICROSOFT_MX = (".outlook.com", ".protection.outlook.com", ".outlook.com.", ".protection.outlook.com.")
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}
OPTIONAL_SCOPES = {"openid", "email", "profile", "https://www.googleapis.com/auth/userinfo.email"}


# --- Detection --------------------------------------------------------------------------------------------


@dataclass
class Detection:
    provider: str  # gmail_oauth | workspace_delegation | imap_smtp | unsupported
    reason: str
    domain: str
    mx: list[str]
    supported: bool = True
    imap_defaults: dict | None = None

    def as_dict(self) -> dict:
        return {"provider": self.provider, "reason": self.reason, "domain": self.domain, "mx": self.mx, "supported": self.supported, "imap_defaults": self.imap_defaults}


def lookup_mx(domain: str) -> list[str]:
    import dns.exception
    import dns.resolver

    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=4)
    except (dns.exception.DNSException, OSError):
        return []
    return [str(r.exchange).rstrip(".").lower() for r in sorted(answers, key=lambda r: r.preference)]


def imap_defaults(domain: str) -> dict:
    return {
        "imap_host": f"mail.{domain}", "imap_port": 993, "imap_security": "ssl",
        "smtp_host": f"mail.{domain}", "smtp_port": 465, "smtp_security": "ssl",
    }


def detect(email: str) -> Detection:
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if domain in GMAIL_DOMAINS:
        return Detection("gmail_oauth", "This is a Gmail address. The owner signs in with Google once and clicks Allow.", domain, [])
    mx = lookup_mx(domain)
    if any(host.endswith(GOOGLE_MX) or host in ("aspmx.l.google.com", "smtp.google.com") for host in mx):
        if WorkspaceDomain.objects.filter(domain=domain, last_test_ok=True).exists():
            return Detection("workspace_delegation", f"{domain} uses Google Workspace with company-wide access set up, so it connects instantly.", domain, mx)
        return Detection("gmail_oauth", f"{domain} uses Google Workspace. The owner signs in with Google once and clicks Allow.", domain, mx)
    if any(host.endswith(MICROSOFT_MX) for host in mx):
        return Detection("unsupported", "Microsoft 365 mailboxes are not supported yet.", domain, mx, supported=False)
    if not mx:
        reason = f"We could not find mail servers for {domain}. Check the address, or enter the server details yourself."
    else:
        reason = f"{domain} is hosted on its own mail server. Enter the mailbox password once; we fill in the server details."
    return Detection("imap_smtp", reason, domain, mx, imap_defaults=imap_defaults(domain))


# --- Invites ----------------------------------------------------------------------------------------------


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def connect_url(token: str) -> str:
    return f"{settings.PUBLIC_APP_URL}/connect/{token}"


@transaction.atomic
def create_invite(mailbox: Mailbox, user, request=None) -> tuple[MailboxInvite, str]:
    """A single-use link. Earlier active links for the same mailbox are revoked so only one works."""
    now = timezone.now()
    MailboxInvite.objects.filter(mailbox=mailbox, used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
    token = secrets.token_urlsafe(32)
    invite = MailboxInvite.objects.create(mailbox=mailbox, token_hash=hash_token(token), expires_at=now + timedelta(hours=settings.MAIL_INVITE_TTL_HOURS), created_by=user)
    record("mailbox.invite_create", request=request, actor=user, mailbox=mailbox, target_type="invite", target_id=invite.pk, metadata={"expires_at": invite.expires_at.isoformat()})
    return invite, token


def revoke_invite(invite: MailboxInvite, user, request=None) -> None:
    if invite.state == "active":
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
        record("mailbox.invite_revoke", request=request, actor=user, mailbox=invite.mailbox, target_type="invite", target_id=invite.pk)


def invite_for_token(token: str) -> MailboxInvite | None:
    if not token or len(token) > 100:
        return None
    return MailboxInvite.objects.select_related("mailbox", "mailbox__office").filter(token_hash=hash_token(token)).first()


def qr_svg(text: str) -> str:
    import io

    import qrcode
    import qrcode.image.svg

    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode()


# --- OAuth ------------------------------------------------------------------------------------------------


class OAuthFailure(Exception):
    """A callback outcome to show the person (not a server error)."""

    def __init__(self, code: str, message: str, **context):
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def oauth_url(mailbox: Mailbox, *, invite: MailboxInvite | None = None, invite_token: str = "", user=None) -> str:
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        from common.errors import ApiError

        raise ApiError("google_not_configured", "Google sign-in is not set up on this server yet. See docs/google-setup.md.", 503)
    verifier, challenge = _pkce()
    state = signing.dumps(
        {
            "m": mailbox.pk,
            "i": invite.pk if invite else None,
            "u": user.pk if user and user.is_authenticated else None,
            "n": secrets.token_hex(8),
            # The verifier and invite token are secrets: encrypt them inside the signed state.
            "v": fernet().encrypt(json.dumps({"verifier": verifier, "token": invite_token}).encode()).decode(),
        },
        salt=STATE_SALT,
        compress=True,
    )
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(settings.GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "login_hint": mailbox.email,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URI}?{urlencode(params)}"


def read_state(state: str) -> dict:
    try:
        data = signing.loads(state or "", salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.SignatureExpired as exc:
        raise OAuthFailure("expired", "This sign-in took too long. Start again.") from exc
    except signing.BadSignature as exc:
        raise OAuthFailure("invalid_state", "This sign-in link is not valid. Start again from the connect page.") from exc
    try:
        secret = json.loads(fernet().decrypt(data["v"].encode()))
    except Exception as exc:  # noqa: BLE001
        raise OAuthFailure("invalid_state", "This sign-in link is not valid. Start again from the connect page.") from exc
    data["verifier"], data["token"] = secret["verifier"], secret.get("token", "")
    return data


def _decode_id_token(id_token: str) -> dict:
    """Claims of an ID token received directly from Google's token endpoint over TLS (OIDC Core 3.1.3.7 allows
    TLS server validation in place of the signature check). Issuer, audience and expiry are still checked."""
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise OAuthFailure("error", "Google returned an unexpected answer. Try again.") from exc
    if claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
        raise OAuthFailure("error", "Google returned an unexpected answer. Try again.")
    if claims.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID:
        raise OAuthFailure("error", "Google returned an unexpected answer. Try again.")
    if int(claims.get("exp", 0)) < int(timezone.now().timestamp()) - 60:
        raise OAuthFailure("error", "Google returned an expired answer. Try again.")
    return claims


def _normalise_scope(scope: str) -> str:
    return "https://www.googleapis.com/auth/userinfo.email" if scope == "email" else scope


def missing_scopes(granted: list[str]) -> list[str]:
    granted_set = {_normalise_scope(s) for s in granted}
    return [s for s in settings.GOOGLE_OAUTH_SCOPES if _normalise_scope(s) not in OPTIONAL_SCOPES and _normalise_scope(s) not in granted_set]


def exchange_code(code: str, verifier: str) -> dict:
    try:
        response = requests.post(
            TOKEN_URI,
            data={
                "code": code, "client_id": settings.GOOGLE_OAUTH_CLIENT_ID, "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI, "grant_type": "authorization_code", "code_verifier": verifier,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise OAuthFailure("error", "Could not reach Google. Check the internet connection and try again.") from exc
    if response.status_code != 200:
        error = ""
        try:
            error = response.json().get("error", "")
        except ValueError:
            pass
        if error == "invalid_grant":
            raise OAuthFailure("expired", "This sign-in expired or was already used. Start again.")
        raise OAuthFailure("error", "Google did not accept the sign-in. Try again.")
    return response.json()


def _revoke_quietly(token: str) -> None:
    try:
        requests.post("https://oauth2.googleapis.com/revoke", data={"token": token}, timeout=10)
    except requests.RequestException:
        pass


def complete_oauth(code: str, state: str, request=None) -> tuple[Mailbox, dict]:
    """Returns (mailbox, state). Raises OAuthFailure with a code the UI explains."""
    data = read_state(state)
    mailbox = Mailbox.objects.select_related("office").filter(pk=data["m"]).first()
    if not mailbox:
        raise OAuthFailure("error", "This mailbox no longer exists.", state=data)
    invite = None
    if data.get("i"):
        invite = MailboxInvite.objects.filter(pk=data["i"], mailbox=mailbox).first()
        if not invite or invite.state != "active":
            raise OAuthFailure("invite_inactive", "This connect link was already used, revoked or has expired. Ask your administrator for a new one.", state=data)
    tokens = exchange_code(code, data["verifier"])
    claims = _decode_id_token(tokens.get("id_token", "")) if tokens.get("id_token") else {}
    signed_in_as = (claims.get("email") or "").lower()
    granted = (tokens.get("scope") or "").split()
    refresh_token = tokens.get("refresh_token")

    if signed_in_as and signed_in_as != mailbox.email.lower():
        if refresh_token:
            _revoke_quietly(refresh_token)
        record("mailbox.connect_wrong_account", request=request, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={"signed_in_as": signed_in_as})
        raise OAuthFailure("wrong_account", f"You signed in as {signed_in_as}, but this link is for {mailbox.email}.", signed_in_as=signed_in_as, expected=mailbox.email, state=data)
    missing = missing_scopes(granted)
    if missing:
        if refresh_token:
            _revoke_quietly(refresh_token)
        raise OAuthFailure("missing_scopes", "Some permissions were not ticked. Communication Manager needs all of them to work with this mailbox.", missing=missing, expected=mailbox.email, state=data)
    if not refresh_token:
        raise OAuthFailure("error", "Google did not return long-term access. Try again.", state=data)

    # Confirm with Gmail itself which mailbox the token opens (authoritative, also covers missing id_token).
    from ..providers.gmail_api import GmailApiProvider

    mailbox.encrypted_credentials = encrypt_json({"refresh_token": refresh_token, "scopes": granted})
    provider = GmailApiProvider(mailbox)
    provider._service = None
    try:
        profile_email = (provider.get_profile().get("emailAddress") or "").lower()
    except Exception as exc:  # noqa: BLE001
        _revoke_quietly(refresh_token)
        raise OAuthFailure("error", "Connected to Google, but could not open the mailbox. Try again.", state=data) from exc
    if profile_email != mailbox.email.lower():
        _revoke_quietly(refresh_token)
        raise OAuthFailure("wrong_account", f"You signed in as {profile_email}, but this link is for {mailbox.email}.", signed_in_as=profile_email, expected=mailbox.email, state=data)

    from django.contrib.auth import get_user_model

    connected_by = get_user_model().objects.filter(pk=data.get("u")).first() if data.get("u") else (invite.created_by if invite else None)
    with transaction.atomic():
        Mailbox.objects.filter(pk=mailbox.pk).update(
            encrypted_credentials=mailbox.encrypted_credentials, granted_scopes=granted, provider="gmail_oauth",
            status=MailboxStatus.CONNECTED, sync_error="", connected_by=connected_by, connected_at=timezone.now(),
        )
        if invite:
            MailboxInvite.objects.filter(pk=invite.pk).update(used_at=timezone.now())
        record("mailbox.connect", request=request, actor=connected_by, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={"via": "invite" if invite else "admin", "scopes": granted})
    mailbox.refresh_from_db()
    from ..tasks import sync_mailbox_task

    transaction.on_commit(lambda: sync_mailbox_task.delay(mailbox.pk, True))
    return mailbox, data
