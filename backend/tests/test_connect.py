"""Connecting mailboxes: invites, the public page, OAuth callback outcomes, detection, health."""

import base64
import json
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from django.conf import settings
from django.core import signing
from django.utils import timezone

from common.crypto import decrypt_json
from modules.audit.models import AuditEvent
from modules.mail.models import Mailbox, MailboxInvite, MailboxStatus
from modules.mail.providers.gmail_api import GmailApiProvider
from modules.mail.services import connect

pytestmark = pytest.mark.django_db
ALL_SCOPES = " ".join(["openid", "https://www.googleapis.com/auth/userinfo.email", "https://mail.google.com/", "https://www.googleapis.com/auth/gmail.settings.basic"])


def id_token(email: str) -> str:
    def b64(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    claims = {"iss": "https://accounts.google.com", "aud": settings.GOOGLE_OAUTH_CLIENT_ID, "email": email, "exp": int(timezone.now().timestamp()) + 3600}
    return f"{b64({'alg': 'RS256'})}.{b64(claims)}.sig"


@pytest.fixture
def google_mailbox(office):
    return Mailbox.objects.create(office=office, email="finance.office@gmail.com", provider="gmail_oauth")


def start(client, token):
    response = client.post("/api/v1/mail/oauth/start/", {"token": token}, format="json")
    assert response.status_code == 200, response.json()
    query = parse_qs(urlparse(response.json()["url"]).query)
    return query


def mock_token(email="finance.office@gmail.com", scope=ALL_SCOPES, refresh="1//refresh-token", status=200, body=None):
    responses.add(responses.POST, connect.TOKEN_URI, status=status, json=body or {"access_token": "ya29.x", "expires_in": 3599, "refresh_token": refresh, "scope": scope, "id_token": id_token(email), "token_type": "Bearer"})
    responses.add(responses.POST, "https://oauth2.googleapis.com/revoke", status=200)


def test_invite_lifecycle_and_public_page(client_for, admin, google_mailbox):
    response = client_for(admin).post(f"/api/v1/mail/mailboxes/{google_mailbox.pk}/invites/")
    assert response.status_code == 201
    body = response.json()
    token = body["url"].rsplit("/", 1)[1]
    assert body["whatsapp_url"].startswith("https://wa.me/?text=")
    assert body["qr_svg"].lstrip().startswith("<?xml") or "<svg" in body["qr_svg"]
    invite = MailboxInvite.objects.get()
    assert invite.token_hash == connect.hash_token(token) and token not in invite.token_hash
    assert invite.expires_at - timezone.now() > timedelta(hours=71)

    public = client_for(None).get(f"/api/v1/mail/connect/{token}/").json()
    assert public["mailbox_email"] == "finance.office@gmail.com"
    assert public["state"] == "active" and "logged" in public["notice"]
    assert client_for(None).get("/api/v1/mail/connect/not-a-token/").status_code == 404

    # A new link revokes the old one.
    client_for(admin).post(f"/api/v1/mail/mailboxes/{google_mailbox.pk}/invites/")
    assert client_for(None).get(f"/api/v1/mail/connect/{token}/").json()["state"] == "revoked"
    assert AuditEvent.objects.filter(action="mailbox.invite_create").count() == 2


def test_oauth_url_has_pkce_offline_consent_and_login_hint(client_for, admin, google_mailbox):
    _, token = connect.create_invite(google_mailbox, admin)
    query = start(client_for(None), token)
    assert query["access_type"] == ["offline"] and query["prompt"] == ["consent"]
    assert query["code_challenge_method"] == ["S256"] and len(query["code_challenge"][0]) >= 43
    assert query["login_hint"] == ["finance.office@gmail.com"]
    assert query["include_granted_scopes"] == ["true"]
    assert "https://mail.google.com/" in query["scope"][0]
    # The state is signed and carries no readable secrets.
    assert token not in query["state"][0]


@responses.activate
def test_callback_success_stores_encrypted_token_and_marks_invite_used(client_for, admin, google_mailbox):
    invite, token = connect.create_invite(google_mailbox, admin)
    state = start(client_for(None), token)["state"][0]
    mock_token()
    with mock.patch.object(GmailApiProvider, "get_profile", return_value={"emailAddress": "finance.office@gmail.com", "historyId": "1"}), \
         mock.patch("modules.mail.tasks.sync_mailbox_task.delay") as sync:
        response = client_for(None).get("/api/v1/mail/oauth/callback/", {"code": "4/abc", "state": state})
    assert response.status_code == 302
    assert response["Location"] == f"/connect/{token}?result=connected"
    google_mailbox.refresh_from_db()
    assert google_mailbox.status == MailboxStatus.CONNECTED
    assert "1//refresh-token" not in google_mailbox.encrypted_credentials
    assert decrypt_json(google_mailbox.encrypted_credentials)["refresh_token"] == "1//refresh-token"
    assert google_mailbox.connected_by == admin
    invite.refresh_from_db()
    assert invite.state == "used"
    sync.assert_called_once_with(google_mailbox.pk, True)
    # The PKCE verifier was sent with the code exchange.
    sent = parse_qs(responses.calls[0].request.body)
    assert sent["code_verifier"][0] and sent["grant_type"] == ["authorization_code"]
    # Reusing the link fails.
    assert client_for(None).post("/api/v1/mail/oauth/start/", {"token": token}, format="json").status_code == 410


@responses.activate
def test_callback_wrong_account_is_rejected_and_token_revoked(client_for, admin, google_mailbox):
    _, token = connect.create_invite(google_mailbox, admin)
    state = start(client_for(None), token)["state"][0]
    mock_token(email="someone.else@gmail.com")
    response = client_for(None).get("/api/v1/mail/oauth/callback/", {"code": "4/abc", "state": state})
    location = urlparse(response["Location"])
    assert location.path == f"/connect/{token}"
    assert parse_qs(location.query) == {"result": ["wrong_account"], "signed_in_as": ["someone.else@gmail.com"]}
    google_mailbox.refresh_from_db()
    assert google_mailbox.encrypted_credentials == "" and google_mailbox.status == MailboxStatus.PENDING
    assert any("revoke" in call.request.url for call in responses.calls)
    assert MailboxInvite.objects.get().state == "active"  # they can try again with the right account


@responses.activate
def test_callback_missing_scopes(client_for, admin, google_mailbox):
    _, token = connect.create_invite(google_mailbox, admin)
    state = start(client_for(None), token)["state"][0]
    mock_token(scope="openid https://www.googleapis.com/auth/userinfo.email https://mail.google.com/")
    response = client_for(None).get("/api/v1/mail/oauth/callback/", {"code": "4/abc", "state": state})
    query = parse_qs(urlparse(response["Location"]).query)
    assert query["result"] == ["missing_scopes"]
    assert query["missing"] == ["https://www.googleapis.com/auth/gmail.settings.basic"]
    google_mailbox.refresh_from_db()
    assert google_mailbox.encrypted_credentials == ""


def test_callback_tampered_state(client_for, admin, google_mailbox):
    _, token = connect.create_invite(google_mailbox, admin)
    state = start(client_for(None), token)["state"][0]
    tampered = state[:-3] + ("AAA" if state[-3:] != "AAA" else "BBB")
    response = client_for(None).get("/api/v1/mail/oauth/callback/", {"code": "4/abc", "state": tampered})
    assert response["Location"] == "/connect/result?result=invalid_state"
    forged = signing.dumps({"m": google_mailbox.pk, "v": "x"}, salt="wrong-salt")
    response = client_for(None).get("/api/v1/mail/oauth/callback/", {"code": "4/abc", "state": forged})
    assert response["Location"] == "/connect/result?result=invalid_state"


def test_callback_expired_state(client_for, admin, google_mailbox):
    _, token = connect.create_invite(google_mailbox, admin)
    state = start(client_for(None), token)["state"][0]
    with mock.patch("modules.mail.services.connect.STATE_MAX_AGE", -1):
        response = client_for(None).get("/api/v1/mail/oauth/callback/", {"code": "4/abc", "state": state})
    assert response["Location"] == "/connect/result?result=expired"


def test_callback_user_denied(client_for, admin, google_mailbox):
    _, token = connect.create_invite(google_mailbox, admin)
    state = start(client_for(None), token)["state"][0]
    response = client_for(None).get("/api/v1/mail/oauth/callback/", {"error": "access_denied", "state": state})
    assert response["Location"] == f"/connect/{token}?result=denied"


@responses.activate
def test_callback_code_exchange_invalid_grant(client_for, admin, google_mailbox):
    _, token = connect.create_invite(google_mailbox, admin)
    state = start(client_for(None), token)["state"][0]
    mock_token(status=400, body={"error": "invalid_grant"})
    response = client_for(None).get("/api/v1/mail/oauth/callback/", {"code": "4/used", "state": state})
    assert parse_qs(urlparse(response["Location"]).query)["result"] == ["expired"]


def test_expired_and_revoked_invites_cannot_start(client_for, admin, google_mailbox):
    invite, token = connect.create_invite(google_mailbox, admin)
    MailboxInvite.objects.filter(pk=invite.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert client_for(None).post("/api/v1/mail/oauth/start/", {"token": token}, format="json").status_code == 410
    invite, token = connect.create_invite(google_mailbox, admin)
    client_for(admin).post(f"/api/v1/mail/mailboxes/{google_mailbox.pk}/invites/{invite.pk}/revoke/")
    assert client_for(None).post("/api/v1/mail/oauth/start/", {"token": token}, format="json").status_code == 410


def test_admin_connect_now_redirects_back_to_mailbox(client_for, admin, google_mailbox):
    url = client_for(admin).post(f"/api/v1/mail/mailboxes/{google_mailbox.pk}/connect/").json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    response = client_for(None).get("/api/v1/mail/oauth/callback/", {"error": "access_denied", "state": state})
    assert response["Location"] == f"/gmail/mailboxes/{google_mailbox.pk}?result=denied"


def test_invalid_grant_marks_needs_reconnect(admin, google_mailbox):
    from google.auth.exceptions import RefreshError

    from common.crypto import encrypt_json
    from modules.mail.services.sync import sync_mailbox

    Mailbox.objects.filter(pk=google_mailbox.pk).update(status=MailboxStatus.CONNECTED, encrypted_credentials=encrypt_json({"refresh_token": "1//x"}), history_id="5")
    with mock.patch("google.oauth2.credentials.Credentials.refresh", side_effect=RefreshError("invalid_grant: Token has been expired or revoked.")):
        assert sync_mailbox(google_mailbox.pk) == "needs_reconnect"
    google_mailbox.refresh_from_db()
    assert google_mailbox.status == MailboxStatus.NEEDS_RECONNECT
    assert AuditEvent.objects.filter(action="mailbox.needs_reconnect").exists()
    # Syncs stop until it is reconnected.
    assert sync_mailbox(google_mailbox.pk) == "skipped:needs_reconnect"


@pytest.mark.parametrize(
    "email,mx,expected",
    [
        ("office@gmail.com", [], "gmail_oauth"),
        ("boss@company.example", ["aspmx.l.google.com", "alt1.aspmx.l.google.com"], "gmail_oauth"),
        ("boss@company.example", ["company-example.mail.protection.outlook.com"], "unsupported"),
        ("boss@company.example", ["mail.company.example"], "imap_smtp"),
        ("boss@company.example", [], "imap_smtp"),
    ],
)
def test_detection(email, mx, expected):
    with mock.patch("modules.mail.services.connect.lookup_mx", return_value=mx):
        result = connect.detect(email)
    assert result.provider == expected
    if expected == "imap_smtp":
        assert result.imap_defaults["imap_host"] == "mail.company.example" and result.imap_defaults["imap_port"] == 993
    if expected == "unsupported":
        assert "Microsoft 365" in result.reason and not result.supported


def test_detection_prefers_workspace_delegation_when_configured(admin):
    from common.crypto import encrypt_json
    from modules.mail.models import WorkspaceDomain

    WorkspaceDomain.objects.create(domain="company.example", encrypted_service_account=encrypt_json({}), client_id="1", service_account_email="sa@x.example", last_test_ok=True)
    with mock.patch("modules.mail.services.connect.lookup_mx", return_value=["aspmx.l.google.com"]):
        assert connect.detect("a@company.example").provider == "workspace_delegation"


def test_microsoft_mailbox_cannot_be_added(client_for, admin, office):
    with mock.patch("modules.mail.services.connect.lookup_mx", return_value=["x.mail.protection.outlook.com"]):
        response = client_for(admin).post("/api/v1/mail/mailboxes/", {"office": office.pk, "email": "ceo@ms.example"}, format="json")
    assert response.status_code == 400
    assert "Microsoft 365" in response.json()["detail"]
