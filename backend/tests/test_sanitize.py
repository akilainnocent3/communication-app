import pytest

from modules.mail.services.sanitize import sanitize_compose_html, sanitize_email_html, text_to_html, with_images

PAYLOADS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    '<iframe src="https://evil.example"></iframe>',
    '<a href="javascript:alert(1)">x</a>',
    '<a href="JaVaScRiPt:alert(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
    '<svg onload="alert(1)"><circle/></svg>',
    '<object data="x.swf"></object><embed src="x.swf">',
    '<form action="https://evil.example"><input name="password"></form>',
    '<div style="background:url(javascript:alert(1))">x</div>',
    '<style>body{background:url(https://track.example/p.gif)}</style>',
    '<meta http-equiv="refresh" content="0;url=https://evil.example">',
    '<base href="https://evil.example/">',
    '<p onclick="steal()" onmouseover="steal()">hi</p>',
    '<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>',
    '<link rel="stylesheet" href="https://evil.example/x.css">',
]
FORBIDDEN = ["<script", "onerror", "onload", "onclick", "onmouseover", "javascript:", "<iframe", "<svg", "<object", "<embed", "<form", "<input", "<style", "<meta", "<base", "<link", "data:text/html", "url("]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_dangerous_markup_is_removed(payload):
    html, _ = sanitize_email_html(payload)
    lowered = html.lower()
    for bad in FORBIDDEN:
        assert bad not in lowered, (payload, html)
    lowered = sanitize_compose_html(payload).lower()
    for bad in FORBIDDEN:
        assert bad not in lowered


def test_remote_images_blocked_until_allowed():
    html, meta = sanitize_email_html('<p>Hi</p><img src="https://track.example/pixel.gif" width="1">')
    assert ' src="https://track.example' not in html
    assert 'data-cm-src="https://track.example/pixel.gif"' in html
    assert meta["remote_images"] == 1
    assert 'src="https://track.example/pixel.gif"' in with_images(html)


def test_attacker_supplied_blocked_attribute_is_dropped():
    html, _ = sanitize_email_html('<img data-cm-src="javascript:alert(1)">')
    assert "javascript" not in with_images(html)


def test_inline_cid_images_resolved_and_data_images_kept():
    html, meta = sanitize_email_html('<img src="cid:logo">', {"logo": "data:image/png;base64,iVBORw0KGgo="})
    assert 'src="data:image/png;base64,iVBORw0KGgo="' in html
    assert meta["remote_images"] == 0


def test_links_open_in_new_tab_without_referrer():
    html, _ = sanitize_email_html('<a href="https://example.com">x</a>')
    assert 'target="_blank"' in html
    assert "noopener" in html and "noreferrer" in html


def test_mismatched_link_text_is_flagged():
    html, meta = sanitize_email_html('<a href="https://evil.example/login">https://mybank.example/login</a><a href="https://www.good.example/a">good.example</a>')
    assert meta["link_warnings"] == [{"text": "https://mybank.example/login", "href": "https://evil.example/login"}]
    assert html.count("data-cm-mismatch") == 1


def test_plain_text_is_escaped_and_linked():
    html = text_to_html("<b>x</b> see https://example.com/a?b=1")
    assert "&lt;b&gt;" in html and 'href="https://example.com/a?b=1"' in html
