"""Shared look for every app: menu bar + colours (same UI as the K8s Ingress work).

Mounted into each container next to app.py (ConfigMap app-common).
"""
import html
import os

WWW_URL = os.environ.get("WWW_URL", "http://www.iam-548.com").rstrip("/")
ADMIN_URL = os.environ.get("ADMIN_URL", "http://admin.iam-548.com").rstrip("/")
API_PREFIX = os.environ.get("API_PREFIX", "api-548").strip("/")
SAMPLE_MSG = "Hello%20I%27m%20June"

NAV_CSS = """
.nav{position:fixed;top:0;left:0;right:0;display:flex;gap:6px;justify-content:center;
flex-wrap:wrap;padding:10px 12px;background:rgba(15,23,42,.88);backdrop-filter:blur(6px);
z-index:10;font-family:'Segoe UI',Tahoma,sans-serif}
.nav a{color:#e2e8f0;text-decoration:none;padding:6px 16px;border-radius:999px;font-size:.95rem}
.nav a:hover{background:rgba(56,189,248,.25)}.nav a.on{background:#38bdf8;color:#0f172a;font-weight:600}
"""


def nav(active, absolute=False):
    """Menu bar linking every service.

    Pages on www.* use relative links, so they work on both www.iam-548.com
    and www.id-548.com. The admin site lives on another host, so it passes
    absolute=True to link back to www.
    """
    base = WWW_URL if absolute else ""
    items = [("portal", base + "/", "Portal"),
             ("research", base + "/research", "Research"),
             ("api", f"{base}/{API_PREFIX}/{SAMPLE_MSG}", "API"),
             ("admin", ADMIN_URL + "/", "Admin &#9998;")]
    return '<nav class="nav">' + "".join(
        f'<a href="{html.escape(h)}" class="{"on" if k == active else ""}">{t}</a>'
        for k, h, t in items) + "</nav>"


def sniff_image(data):
    """Content-Type from the first bytes of an image (photo key name may not match)."""
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG"):
        return "image/png", "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", "gif"
    return None, None
