"""portal-548: www.iam-548.com/ shows the student's photo, name and ID.

Routes
  /          photo + name + student ID
  /photo     the photo file
  /healthz   probe endpoint

Data comes from ConfigMap portal-data, mounted at /data:
  /data/portal.json   {"name", "name_en", "student_id", "course", "updated"}
  /data/photo.*       the photo (binaryData)
admin-548 edits that ConfigMap. Files are read on every request, so a new
value shows up as soon as the pod sees the updated ConfigMap.
"""
import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/common")
from common import NAV_CSS, nav, sniff_image  # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))
DATA_DIR = os.environ.get("DATA_DIR", "/data")

STYLE = """
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;
background:linear-gradient(135deg,#1e3c72,#2a5298);min-height:100vh;display:flex;
align-items:center;justify-content:center;color:#1f2937;padding:76px 16px 16px}
.card{background:#fff;border-radius:18px;box-shadow:0 20px 50px rgba(0,0,0,.3);
padding:40px;max-width:520px;width:100%;text-align:center}
img{width:200px;height:200px;object-fit:cover;border-radius:50%;border:6px solid #2a5298}
h1{margin:20px 0 6px;font-size:1.8rem}h2{margin:0;color:#6b7280;font-weight:500;font-size:1.1rem}
.id{display:inline-block;margin-top:16px;background:#2a5298;color:#fff;padding:8px 22px;
border-radius:999px;font-size:1.3rem;letter-spacing:2px}
.pod{margin-top:22px;color:#9ca3af;font-size:.75rem}
"""


def load():
    try:
        with open(os.path.join(DATA_DIR, "portal.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"name": "Student Name", "name_en": "", "student_id": "00000000", "course": ""}


def find_photo():
    if not os.path.isdir(DATA_DIR):
        return None
    for f in sorted(os.listdir(DATA_DIR)):
        if f.startswith("photo."):
            return os.path.join(DATA_DIR, f)
    return None


def page(title, body):
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}{NAV_CSS}</style></head>
<body>{nav("portal")}<div class="card">{body}
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            return self.send(200, "ok", "text/plain")
        if path == "/photo":
            p = find_photo()
            if not p:
                return self.send(404, "no photo", "text/plain")
            with open(p, "rb") as fh:
                data = fh.read()
            return self.send(200, data, sniff_image(data)[0] or "application/octet-stream")
        if path == "/":
            d = load()
            en = f"<h2>{html.escape(d.get('name_en', ''))}</h2>" if d.get("name_en") else ""
            body = (f'<img src="/photo" alt="photo">'
                    f"<h1>{html.escape(d.get('name', ''))}</h1>{en}"
                    f'<div class="id">{html.escape(d.get("student_id", ""))}</div>'
                    f"<p>{html.escape(d.get('course', ''))}</p>"
                    f'<div class="pod">served by pod {html.escape(os.environ.get("HOSTNAME", "-"))}</div>')
            return self.send(200, page("Portal - " + d.get("student_id", ""), body))
        return self.send(404, page("404", "<h1>404</h1><p>Not found</p>"))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"portal-548 listening on :{PORT}, data={DATA_DIR}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
