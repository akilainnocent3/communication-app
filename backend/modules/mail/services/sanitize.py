"""Server-side sanitising of email HTML (nh3 allowlist). The client runs DOMPurify again and renders the
result in a sandboxed iframe with a strict CSP, so this is the first of three layers.

Remote images are blocked by default: their URL moves to `data-cm-src` and `src` is dropped. When the user
asks to see images (or trusts the sender), `with_images()` swaps them back on the way out.
"""

from __future__ import annotations

import html as html_lib
import re
from urllib.parse import urlparse

import nh3

TAGS = {
    "a", "abbr", "address", "b", "bdi", "bdo", "blockquote", "br", "caption", "center", "cite", "code", "col",
    "colgroup", "dd", "del", "details", "dfn", "div", "dl", "dt", "em", "figcaption", "figure", "font", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd", "li", "mark", "ol", "p", "pre", "q", "s", "samp",
    "small", "span", "strike", "strong", "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead",
    "tr", "tt", "u", "ul", "wbr",
}
COMMON = {"style", "dir", "lang", "title", "align", "valign", "width", "height", "bgcolor", "class"}
ATTRIBUTES = {
    "*": COMMON,
    "a": {"href", "name", "target"},
    "img": {"src", "alt", "border"},
    "font": {"color", "face", "size"},
    "table": {"border", "cellpadding", "cellspacing", "summary"},
    "td": {"colspan", "rowspan", "nowrap"},
    "th": {"colspan", "rowspan", "nowrap", "scope"},
    "col": {"span"},
    "colgroup": {"span"},
    "ol": {"start", "type", "reversed"},
    "li": {"value"},
    "blockquote": {"cite", "type"},
}
STYLE_PROPERTIES = {
    "background-color", "border", "border-bottom", "border-collapse", "border-color", "border-left", "border-radius",
    "border-right", "border-spacing", "border-style", "border-top", "border-width", "color", "direction", "display",
    "float", "font", "font-family", "font-size", "font-style", "font-variant", "font-weight", "height",
    "letter-spacing", "line-height", "list-style-type", "margin", "margin-bottom", "margin-left", "margin-right",
    "margin-top", "max-width", "min-width", "padding", "padding-bottom", "padding-left", "padding-right",
    "padding-top", "table-layout", "text-align", "text-decoration", "text-indent", "text-transform",
    "vertical-align", "white-space", "width", "word-break", "word-wrap",
}
URL_SCHEMES = {"http", "https", "mailto", "tel", "cid", "data"}
_INLINE_IMAGE = re.compile(r"^data:image/(png|jpe?g|gif|webp|bmp);base64,[a-z0-9+/=\s]+$", re.I)


def _attribute_filter(tag: str, attr: str, value: str):
    if attr in ("src", "href", "cite"):
        lowered = value.strip().lower()
        if lowered.startswith("data:"):
            # data: only for inline images; never for links (data:text/html phishing pages).
            return value if tag == "img" and attr == "src" and _INLINE_IMAGE.match(lowered) else None
        if lowered.startswith("cid:"):
            return None  # unresolved inline image reference
    if attr == "style" and "url(" in value.lower():
        return None
    if attr == "class":
        return None
    return value


def _clean(html: str) -> str:
    return nh3.clean(
        html,
        tags=TAGS,
        clean_content_tags={"script", "style", "title", "head", "noscript", "template"},
        attributes=ATTRIBUTES,
        attribute_filter=_attribute_filter,
        link_rel="noopener noreferrer nofollow",
        set_tag_attribute_values={"a": {"target": "_blank"}},
        url_schemes=URL_SCHEMES,
        filter_style_properties=STYLE_PROPERTIES,
        strip_comments=True,
    )


_IMG_SRC = re.compile(r"(<img\b[^>]*?)\ssrc=\"(https?://[^\"]*)\"", re.I)
_BLOCKED = re.compile(r"(<img\b[^>]*?)\sdata-cm-src=\"([^\"]*)\"", re.I)
_ANCHOR = re.compile(r"<a\b([^>]*)\shref=\"([^\"]*)\"([^>]*)>(.*?)</a>", re.I | re.S)
_DOMAIN_IN_TEXT = re.compile(r"^(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:[/:?#].*)?$", re.I)


def _resolve_cid(html: str, inline_images: dict[str, str]) -> str:
    def replace(match):
        cid = match.group(2)
        return f'{match.group(1)}"{inline_images.get(cid, "cid:" + cid)}"'

    return re.sub(r"(src=)[\"']cid:([^\"']+)[\"']", replace, html, flags=re.I)


def _host(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _flag_mismatched_links(html: str) -> tuple[str, list[dict]]:
    """Mark links whose visible text is a different domain than where they go (classic phishing)."""
    warnings: list[dict] = []

    def check(match):
        attrs_before, href, attrs_after, inner = match.groups()
        text = html_lib.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        shown = _DOMAIN_IN_TEXT.match(text)
        if shown and href.lower().startswith(("http://", "https://")):
            shown_host = shown.group(1).lower().removeprefix("www.")
            real_host = _host(href)
            if real_host and shown_host != real_host and not real_host.endswith("." + shown_host):
                warnings.append({"text": text[:200], "href": href[:500]})
                title = html_lib.escape(f"Careful: this link goes to {real_host}, not {shown_host}", quote=True)
                return f'<a{attrs_before} href="{href}"{attrs_after} data-cm-mismatch="1" title="{title}">{inner}</a>'
        return match.group(0)

    return _ANCHOR.sub(check, html), warnings


def sanitize_email_html(html: str, inline_images: dict[str, str] | None = None) -> tuple[str, dict]:
    """Returns (safe_html, meta). meta: remote_images (int), link_warnings (list)."""
    if not html:
        return "", {"remote_images": 0, "link_warnings": []}
    resolved = _resolve_cid(html, inline_images or {})
    cleaned = _clean(resolved)
    remote = 0

    def block(match):
        nonlocal remote
        remote += 1
        return f'{match.group(1)} data-cm-src="{match.group(2)}"'

    cleaned = _IMG_SRC.sub(block, cleaned)
    cleaned, warnings = _flag_mismatched_links(cleaned)
    return cleaned, {"remote_images": remote, "link_warnings": warnings}


def with_images(safe_html: str) -> str:
    """Re-enable remote images in already-sanitised HTML (the URLs passed the allowlist on the way in)."""
    return _BLOCKED.sub(lambda m: f'{m.group(1)} src="{m.group(2)}"', safe_html)


def text_to_html(text: str) -> str:
    """Plain-text bodies rendered as HTML: escaped, links made clickable, line breaks kept."""
    escaped = html_lib.escape(text or "")
    linked = re.sub(r"(https?://[^\s<>&\"]+)", r'<a href="\1" target="_blank" rel="noopener noreferrer nofollow">\1</a>', escaped)
    return f'<div style="white-space: pre-wrap; font-family: inherit">{linked}</div>'


def sanitize_compose_html(html: str) -> str:
    """HTML written in our editor (outgoing mail, signatures, templates): same allowlist, images kept."""
    return _clean(html or "")
