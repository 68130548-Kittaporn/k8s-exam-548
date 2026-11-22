"""api-548: www.iam-548.com/api-548/<message> shows <message> in large text, centred.

Routes
  /api-548/<message>   big centred message (URL-decoded, HTML-escaped)
  /api-548             usage hint
  /healthz             probe endpoint
"""
import html
import os
import sys
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/common")
from common import API_PREFIX, NAV_CSS, nav  # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))
BASE = "/" + API_PREFIX

PAGE = """<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>
html,body{{margin:0;height:100%}}
body{{display:flex;align-items:center;justify-content:center;flex-direction:column;
background:#0f172a;color:#f8fafc;font-family:'Segoe UI',Tahoma,sans-serif;padding:70px 16px 90px;
box-sizing:border-box;text-align:center}}
h1{{margin:0;font-size:clamp(2.5rem,10vw,9rem);line-height:1.1;word-break:break-word;
background:linear-gradient(90deg,#38bdf8,#a78bfa,#f472b6);-webkit-background-clip:text;
background-clip:text;color:transparent}}
{nav_css}
.nav{{background:rgba(30,41,59,.9)}}
form{{position:fixed;bottom:24px;display:flex;gap:8px;width:min(480px,calc(100% - 32px))}}
form input{{flex:1;padding:10px 14px;border-radius:999px;border:1px solid #334155;
background:#1e293b;color:#f8fafc;font:inherit}}
form button{{padding:10px 20px;border-radius:999px;border:0;background:#a78bfa;color:#0f172a;
font-weight:600;cursor:pointer}}
</style></head><body>{nav}<h1>{msg}</h1>
<form onsubmit="var v=this.m.value.trim();if(v)location.href='{base}/'+encodeURIComponent(v);return false">
<input name="m" placeholder="&#3614;&#3636;&#3617;&#3614;&#3660;&#3586;&#3657;&#3629;&#3588;&#3623;&#3634;&#3617;..." autocomplete="off"><button>Show</button></form>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self.send(200, "ok", "text/plain")
        if path == BASE or path.startswith(BASE + "/"):
            raw = path[len(BASE) + 1:]
            msg = unquote(raw).strip()
            if msg:
                shown, title = html.escape(msg), html.escape(msg[:60])
            else:
                shown = title = f"Usage: {BASE}/&lt;message&gt;"
            return self.send(200, PAGE.format(title=title, msg=shown, nav=nav("api"),
                                              nav_css=NAV_CSS, base=BASE))
        return self.send(404, "not found", "text/plain")

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"api-548 listening on :{PORT}, prefix={BASE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
