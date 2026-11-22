"""app-research: www.iam-548.com/research shows the seminar research summary.

Routes
  /research   the summary (read-only; it is edited on admin.iam-548.com)
  /healthz    probe endpoint

Data comes from ConfigMap research-data, mounted at /data:
  /data/research.json   {"title", "body", "updated"}
"""
import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/common")
from common import NAV_CSS, nav  # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))
DATA_FILE = os.path.join(os.environ.get("DATA_DIR", "/data"), "research.json")

STYLE = """
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;
background:#f1f5f9;color:#1e293b;padding:64px 16px 16px}
.wrap{max-width:860px;margin:24px auto;background:#fff;border-radius:14px;
box-shadow:0 10px 30px rgba(0,0,0,.08);padding:36px}
h1{margin-top:0;color:#0f766e;line-height:1.35}
p{line-height:1.9;font-size:1.05rem;text-align:justify}
.meta{color:#64748b;font-size:.85rem;border-top:1px solid #e2e8f0;padding-top:12px;margin-top:28px}
"""


def load():
    try:
        with open(DATA_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"title": "Research summary", "body": "(empty)", "updated": None}


def paragraphs(text):
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>" for b in blocks)


def page(title, inner):
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}{NAV_CSS}</style></head>
<body>{nav("research")}<div class="wrap">{inner}
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = self.path.split("?", 1)[0].rstrip("/") or "/"
        if p == "/healthz":
            return self.send(200, "ok", "text/plain")
        if p == "/research":
            d = load()
            meta = (f"Last updated: {html.escape(str(d.get('updated') or '-'))}"
                    f" &middot; served by pod {html.escape(os.environ.get('HOSTNAME', '-'))}")
            return self.send(200, page(d["title"], f"<h1>{html.escape(d['title'])}</h1>"
                                       f"{paragraphs(d['body'])}<p class='meta'>{meta}</p>"))
        return self.send(404, page("404", "<h1>404</h1>"))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"app-research listening on :{PORT}, data={DATA_FILE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
