"""admin-548: admin.iam-548.com, choose which data to edit (portal or research).

Routes
  GET  /                 two buttons: edit Portal / edit Research
  GET  /portal           form: name, English name, student ID, course, photo
  POST /portal           save to ConfigMap portal-data, restart portal-548
  GET  /portal/photo     current photo (read from the ConfigMap)
  GET  /research         form: title + summary
  POST /research         save to ConfigMap research-data, restart app-research
  GET  /healthz          probe endpoint

How saving works
  The data of portal-548 and app-research lives in two ConfigMaps. This app
  calls the Kubernetes API with its ServiceAccount token. RBAC (k8s/40-admin.yaml)
  only lets it get/patch those two ConfigMaps and those two Deployments.
  After patching a ConfigMap it sets the restartedAt annotation on the
  Deployment (same as `kubectl rollout restart`), so the new pods mount the
  new data within a few seconds.
"""
import base64
import html
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/common")
from common import NAV_CSS, nav, sniff_image  # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))
SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
K8S_API = os.environ.get("K8S_API", "https://kubernetes.default.svc").rstrip("/")
MAX_BODY = 2_000_000          # form post incl. the base64 photo
MAX_PHOTO = 700_000           # a ConfigMap is limited to 1 MiB in total

TARGETS = {  # what each edit page changes
    "portal": {"configmap": "portal-data", "key": "portal.json", "deployment": "portal-548"},
    "research": {"configmap": "research-data", "key": "research.json", "deployment": "app-research"},
}


def read_sa(name, default=""):
    try:
        with open(os.path.join(SA_DIR, name), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return default


NS = os.environ.get("NAMESPACE") or read_sa("namespace", "iam-548")
_ctx = None


def tls():
    global _ctx
    if _ctx is None and K8S_API.startswith("https"):
        _ctx = ssl.create_default_context(cafile=os.path.join(SA_DIR, "ca.crt"))
    return _ctx


def k8s(method, path, body=None):
    """Call the Kubernetes API. The token is re-read each time because it rotates."""
    req = urllib.request.Request(K8S_API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", "Bearer " + read_sa("token"))
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/merge-patch+json")
    with urllib.request.urlopen(req, context=tls(), timeout=10) as r:
        return json.load(r)


def get_cm(name):
    return k8s("GET", f"/api/v1/namespaces/{NS}/configmaps/{name}")


def patch_cm(name, data=None, binary=None):
    body = {}
    if data is not None:
        body["data"] = data
    if binary is not None:
        body["binaryData"] = binary
    return k8s("PATCH", f"/api/v1/namespaces/{NS}/configmaps/{name}", body)


def restart(deployment):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    k8s("PATCH", f"/apis/apps/v1/namespaces/{NS}/deployments/{deployment}",
        {"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": stamp}}}}})


def load(target):
    t = TARGETS[target]
    cm = get_cm(t["configmap"])
    return json.loads((cm.get("data") or {}).get(t["key"], "{}")), cm


STYLE = """
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;
background:#f1f5f9;color:#1e293b;padding:64px 16px 16px}
.wrap{max-width:860px;margin:24px auto;background:#fff;border-radius:14px;
box-shadow:0 10px 30px rgba(0,0,0,.08);padding:36px}
h1{margin-top:0;color:#0f766e;line-height:1.35}
.meta{color:#64748b;font-size:.85rem;border-top:1px solid #e2e8f0;padding-top:12px;margin-top:28px}
label{font-weight:600;display:block;margin:14px 0 6px}
input,textarea{width:100%;font:inherit;padding:10px;border:1px solid #cbd5e1;border-radius:8px}
textarea{min-height:420px;line-height:1.7}
button,.btn{margin-top:16px;background:#0f766e;color:#fff;border:0;padding:12px 28px;
border-radius:8px;font-size:1rem;cursor:pointer;text-decoration:none;display:inline-block}
.ok{background:#dcfce7;color:#166534;padding:10px 14px;border-radius:8px}
.err{background:#fee2e2;color:#991b1b;padding:10px 14px;border-radius:8px;white-space:pre-wrap}
.badge{display:inline-block;background:#fef3c7;color:#92400e;padding:2px 10px;border-radius:999px;font-size:.8rem}
.choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:20px}
.choice{display:block;border:2px solid #e2e8f0;border-radius:14px;padding:26px;text-decoration:none;
color:#1e293b;transition:.15s}
.choice:hover{border-color:#0f766e;box-shadow:0 8px 24px rgba(15,118,110,.15);transform:translateY(-2px)}
.choice .icon{font-size:2.4rem}.choice h2{margin:10px 0 6px;color:#0f766e}
.choice p{margin:0;color:#64748b;line-height:1.6}
.photo{width:120px;height:120px;object-fit:cover;border-radius:50%;border:4px solid #2a5298}
.back{color:#0f766e;text-decoration:none}
"""


def page(title, inner):
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}{NAV_CSS}</style></head>
<body>{nav("admin", absolute=True)}<div class="wrap">{inner}
</div></body></html>"""


def home():
    return page("Admin - iam-548", f"""
<span class="badge">ADMIN</span><h1>เลือกข้อมูลที่ต้องการแก้ไข</h1>
<div class="choices">
  <a class="choice" href="/portal"><div class="icon">&#128100;</div><h2>แก้ไข Portal</h2>
    <p>รูป ชื่อ และรหัสนักศึกษา ที่แสดงบน www.iam-548.com<br>(ConfigMap portal-data &rarr; portal-548)</p></a>
  <a class="choice" href="/research"><div class="icon">&#128218;</div><h2>แก้ไข Research</h2>
    <p>หัวข้อและสรุปงานวิจัย ที่แสดงบน www.iam-548.com/research<br>(ConfigMap research-data &rarr; app-research)</p></a>
</div>
<p class="meta">namespace {html.escape(NS)} &middot; served by pod {html.escape(os.environ.get("HOSTNAME", "-"))}</p>""")


def notice(saved, error):
    if error:
        return f'<p class="err">&#10008; {html.escape(error)}</p>'
    if saved:
        return (f'<p class="ok">&#10004; บันทึกแล้ว และสั่ง rollout restart {html.escape(saved)} '
                f'(หน้าเว็บจะเปลี่ยนภายในประมาณ 10-20 วินาที)</p>')
    return ""


def portal_form(d, has_photo, saved="", error=""):
    photo = '<img class="photo" src="/portal/photo?t=%d" alt="photo">' % time.time() if has_photo else "(ไม่มีรูป)"
    f = lambda k: html.escape(str(d.get(k, "")))  # noqa: E731
    return page("Edit portal", f"""
<a class="back" href="/">&larr; กลับ</a><br><span class="badge">ADMIN</span><h1>แก้ไขข้อมูล Portal</h1>{notice(saved, error)}
<form method="post" action="/portal">
<label>รูปปัจจุบัน</label>{photo}
<label for="file">เปลี่ยนรูป (jpg / png / webp ไม่เกิน 700 KB, เว้นว่างถ้าไม่เปลี่ยน)</label>
<input id="file" type="file" accept="image/*">
<input type="hidden" name="photo_b64" id="photo_b64">
<label for="name">ชื่อ-นามสกุล</label><input id="name" name="name" value="{f('name')}">
<label for="name_en">ชื่อภาษาอังกฤษ</label><input id="name_en" name="name_en" value="{f('name_en')}">
<label for="student_id">รหัสนักศึกษา</label><input id="student_id" name="student_id" value="{f('student_id')}">
<label for="course">รายวิชา</label><input id="course" name="course" value="{f('course')}">
<button type="submit">Save</button></form>
<p class="meta">Last updated: {f('updated') or '-'}</p>
<script>
document.getElementById('file').onchange = function () {{
  var file = this.files[0], out = document.getElementById('photo_b64');
  out.value = '';
  if (!file) return;
  if (file.size > {MAX_PHOTO}) {{ alert('รูปใหญ่เกิน 700 KB'); this.value = ''; return; }}
  var r = new FileReader();
  r.onload = function () {{ out.value = r.result.split(',')[1]; }};
  r.readAsDataURL(file);
}};
</script>""")


def research_form(d, saved="", error=""):
    f = lambda k: html.escape(str(d.get(k, "")))  # noqa: E731
    return page("Edit research", f"""
<a class="back" href="/">&larr; กลับ</a><br><span class="badge">ADMIN</span><h1>แก้ไขสรุปงานวิจัย</h1>{notice(saved, error)}
<form method="post" action="/research">
<label for="title">Title</label><input id="title" name="title" value="{f('title')}">
<label for="body">Summary (300-500 words; blank line = new paragraph)</label>
<textarea id="body" name="body">{f('body')}</textarea>
<button type="submit">Save</button></form>
<p class="meta">Last updated: {f('updated') or '-'}</p>""")


def api_error(e):
    if isinstance(e, urllib.error.HTTPError):
        detail = e.read().decode(errors="replace")[:500]
        return f"Kubernetes API {e.code}: {detail}"
    return f"Kubernetes API error: {e}"


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def route(self):
        return self.path.split("?", 1)[0].rstrip("/") or "/"

    def do_GET(self):
        p = self.route()
        if p == "/healthz":
            return self.send(200, "ok", "text/plain")
        if p == "/":
            return self.send(200, home())
        try:
            if p == "/portal":
                d, cm = load("portal")
                return self.send(200, portal_form(d, any(k.startswith("photo.") for k in cm.get("binaryData") or {})))
            if p == "/portal/photo":
                cm = get_cm("portal-data")
                for k, v in sorted((cm.get("binaryData") or {}).items()):
                    if k.startswith("photo."):
                        data = base64.b64decode(v)
                        return self.send(200, data, sniff_image(data)[0] or "application/octet-stream")
                return self.send(404, "no photo", "text/plain")
            if p == "/research":
                return self.send(200, research_form(load("research")[0]))
        except Exception as e:  # API down or RBAC denied: show it on the page
            return self.send(502, page("Error", f'<p class="err">{html.escape(api_error(e))}</p>'))
        return self.send(404, page("404", "<h1>404</h1>"))

    def do_POST(self):
        p = self.route()
        if p not in ("/portal", "/research"):
            return self.send(404, "not found", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.send(413, "too large", "text/plain")
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        get = lambda k: form.get(k, [""])[0].strip()  # noqa: E731
        stamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
        t = TARGETS[p[1:]]
        if p == "/portal":
            d = {"name": get("name"), "name_en": get("name_en"), "student_id": get("student_id"),
                 "course": get("course"), "updated": stamp}
        else:
            d = {"title": get("title") or "Research summary", "body": get("body"), "updated": stamp}
        try:
            binary, has_photo = None, False
            if p == "/portal":
                _, cm = load("portal")
                old = [k for k in (cm.get("binaryData") or {}) if k.startswith("photo.")]
                has_photo = bool(old)
                if get("photo_b64"):
                    raw = base64.b64decode(get("photo_b64"))
                    ctype, ext = sniff_image(raw)
                    if not ctype:
                        raise ValueError("ไฟล์ที่เลือกไม่ใช่รูป jpg / png / webp / gif")
                    if len(raw) > MAX_PHOTO:
                        raise ValueError("รูปใหญ่เกิน 700 KB")
                    binary = {k: None for k in old}          # null removes the old photo key
                    binary["photo." + ext] = base64.b64encode(raw).decode()
                    has_photo = True
            patch_cm(t["configmap"], {t["key"]: json.dumps(d, ensure_ascii=False, indent=2)}, binary)
            restart(t["deployment"])
            saved, error = t["deployment"], ""
        except Exception as e:
            saved = ""
            error = str(e) if isinstance(e, ValueError) else api_error(e)
        if p == "/portal":
            return self.send(200 if not error else 400, portal_form(d, has_photo, saved, error))
        return self.send(200 if not error else 400, research_form(d, saved, error))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"admin-548 listening on :{PORT}, namespace={NS}, api={K8S_API}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
