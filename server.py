#!/usr/bin/env python3
"""Relais X96 Remote : sert la page web et traduit les boutons en commandes ADB.
Aucune dépendance Python. Variables : ADB_TARGET (def. localhost:5555), PORT (def. 8080), ADB (def. adb)."""
import json, os, re, shlex, subprocess, time, urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ADB = os.environ.get("ADB", "adb")
TARGET = os.environ.get("ADB_TARGET", "localhost:5555")
PORT = int(os.environ.get("PORT", "8080"))
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
IPTV = "https://iptv-org.github.io/iptv/"

KEYS = {"up": 19, "down": 20, "left": 21, "right": 22, "ok": 23, "back": 4, "home": 3,
        "menu": 82, "power": 26, "volup": 24, "voldown": 25, "mute": 164, "play": 85,
        "ff": 90, "rw": 89, "chup": 166, "chdown": 167, "info": 165, "del": 67,
        **{str(i): 7 + i for i in range(10)}}
APPS = {"settings": "am start -a android.settings.SETTINGS",
        "wifi": "am start -a android.settings.WIFI_SETTINGS"}

def _bin_ok():
    try:
        return subprocess.run([ADB, "version"], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False

# Mode "bin" : programme adb. Mode "py" : ADB en Python pur (paquet adb-shell), utile si adb ne démarre pas.
MODE = os.environ.get("ADB_MODE") or ("bin" if _bin_ok() else "py")
_dev = None

def _py_connect():
    global _dev
    from adb_shell.adb_device import AdbDeviceTcp
    from adb_shell.auth.keygen import keygen
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner
    host, port = TARGET.rsplit(":", 1)
    key = os.path.expanduser("~/.x96_adbkey")
    if not os.path.exists(key):
        keygen(key)
    signer = PythonRSASigner(open(key + ".pub").read(), open(key).read())
    d = AdbDeviceTcp(host, int(port), default_transport_timeout_s=9.0)
    d.connect(rsa_keys=[signer], auth_timeout_s=30)
    _dev = d

def connect():
    global _dev
    try:
        if MODE == "py":
            _py_connect()
            return True, "connected (py)"
        p = subprocess.run([ADB, "connect", TARGET], capture_output=True, text=True, timeout=10)
        return "connected" in p.stdout.lower(), p.stdout.strip() or p.stderr.strip()
    except Exception as e:
        _dev = None
        return False, str(e)

def is_connected():
    if MODE == "py":
        return _dev is not None and _dev.available
    p = subprocess.run([ADB, "-s", TARGET, "get-state"], capture_output=True, text=True, timeout=10)
    return p.returncode == 0 and "device" in p.stdout

def _run(cmd):
    if MODE == "py":
        if _dev is None or not _dev.available:
            ok, out = connect()
            if not ok: return False, out
        return True, str(_dev.shell(cmd)).strip()
    p = subprocess.run([ADB, "-s", TARGET, "shell", cmd], capture_output=True, text=True, timeout=10)
    return p.returncode == 0, (p.stdout + p.stderr).strip()

def shell(cmd):
    try:
        ok, out = _run(cmd)
        if not ok and MODE == "bin" and ("offline" in out or "not found" in out or "no devices" in out):
            connect()
            ok, out = _run(cmd)
        return ok, out
    except Exception as e:
        return False, str(e)

HERE = os.path.dirname(os.path.abspath(__file__))

def _git(*a):
    p = subprocess.run(["git", "-C", HERE, *a], capture_output=True, text=True, timeout=90)
    return p.returncode == 0, (p.stdout + p.stderr).strip()

def update():
    """git pull ; relance le relais si server.py a changé. Les fichiers web sont relus à chaque requête."""
    ok, old = _git("rev-parse", "HEAD")
    ok2, out = _git("pull", "--ff-only")
    if not ok2:
        return False, out, False
    _, new = _git("rev-parse", "HEAD")
    restart = False
    if old != new:
        _, files = _git("diff", "--name-only", old, new)
        restart = "server.py" in files.split()
    return True, ("Mis à jour" if old != new else "Déjà à jour"), restart

def restart_soon():
    import threading, sys
    threading.Timer(1.0, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()

_cache = {}
def fetch(url, ttl=3600):
    t = _cache.get(url)
    if t and time.time() - t[0] < ttl:
        return t[1]
    with urllib.request.urlopen(url, timeout=25) as r:
        data = r.read().decode("utf-8", "replace")
    _cache[url] = (time.time(), data)
    return data

def parse_m3u(text):
    out, meta = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            name = line.rsplit(",", 1)[-1].strip()
            g = lambda k: (re.search(k + r'="([^"]*)"', line) or [None, ""])[1]
            meta = {"name": name, "logo": g("tvg-logo"), "group": g("group-title")}
        elif line and not line.startswith("#") and meta:
            meta["url"] = line
            out.append(meta)
            meta = None
    return out

FOOT = re.compile(r"foot|soccer|f[uú]tbol|calcio|ligue|liga|premier|champions|uefa|fifa|bein|dazn|bundesliga|sport ?5|sport ?1|one sport|eleven|sky sport|canal\+? ?sport|rmc|eurosport|arena|supersport|\bsport", re.I)

def channels(country, category, q, limit, mode=""):
    if mode in ("foot", "sport"):
        items = parse_m3u(fetch(IPTV + "categories/sports.m3u"))
        if country:
            try:
                items += parse_m3u(fetch(IPTV + f"countries/{country}.m3u"))
            except Exception:
                pass
        if mode == "foot":
            items = [c for c in items if FOOT.search(c["name"])]
        seen, out = set(), []
        for c in items:
            if c["url"] not in seen:
                seen.add(c["url"]); out.append(c)
        items = out
    else:
        src = f"categories/{category}.m3u" if category else f"countries/{country}.m3u"
        items = parse_m3u(fetch(IPTV + src))
    q = q.lower()
    if q:
        items = [c for c in items if q in c["name"].lower()]
    return items[:limit]

def launch_app(pkg):
    for cat in ("android.intent.category.LAUNCHER", "android.intent.category.LEANBACK_LAUNCHER"):
        ok, out = shell(f"monkey -p {pkg} -c {cat} 1")
        if ok and "No activities found" not in out and "monkey aborted" not in out:
            return True, out
    ok, out = shell(f"cmd package resolve-activity --brief -c android.intent.category.LAUNCHER {pkg}")
    comp = out.strip().splitlines()[-1].strip() if ok and out.strip() else ""
    if "/" in comp:
        return shell(f"am start -n {comp}")
    return False, "Cette appli n'a pas d'écran à lancer"

def open_stream(url, package=""):
    if not re.match(r"^https?://", url):
        return False, "URL invalide"
    cmd = f"am start -a android.intent.action.VIEW -d {shlex.quote(url)} -t 'video/*'"
    if package:
        if not re.match(r"^[A-Za-z0-9_.]+$", package):
            return False, "package invalide"
        cmd += f" -p {package}"
    return shell(cmd)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path == "/api/status":
                return self.send(200, {"connected": is_connected(), "target": TARGET, "mode": MODE})
            if u.path == "/api/channels":
                items = channels(q.get("country", "fr"), q.get("category", ""), q.get("q", ""), int(q.get("limit", "300")), q.get("mode", ""))
                return self.send(200, items)
        except Exception as e:
            return self.send(502, {"ok": False, "error": str(e)})
        name = "index.html" if u.path == "/" else u.path.lstrip("/")
        path = os.path.realpath(os.path.join(WEB, name))
        if not path.startswith(os.path.realpath(WEB) + os.sep) or not os.path.isfile(path):
            return self.send(404, {"error": "not found"})
        ct = {"html": "text/html; charset=utf-8", "json": "application/json", "png": "image/png",
              "js": "text/javascript", "webmanifest": "application/manifest+json"}.get(path.rsplit(".", 1)[-1], "application/octet-stream")
        self.send(200, open(path, "rb").read(), ct)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
            p = self.path
            if p == "/api/connect":
                ok, out = connect()
            elif p == "/api/update":
                ok, out, rs = update()
                if rs: restart_soon()
                return self.send(200 if ok else 500, {"ok": ok, "out": out, "restart": rs})
            elif p == "/api/key":
                code = KEYS.get(d.get("key"))
                if code is None: return self.send(400, {"ok": False, "error": "touche inconnue"})
                ok, out = shell(f"input keyevent {code}")
            elif p == "/api/text":
                t = str(d.get("text", ""))
                t = re.sub(r"[^A-Za-z0-9@._\-+ ]", "", t).replace(" ", "%s")
                ok, out = shell(f"input text {shlex.quote(t)}")
            elif p == "/api/open":
                ok, out = open_stream(str(d.get("url", "")), str(d.get("package", "")))
            elif p == "/api/launch":
                pkg = str(d.get("package", ""))
                if pkg in APPS: ok, out = shell(APPS[pkg])
                elif re.match(r"^[A-Za-z0-9_.]+$", pkg):
                    ok, out = launch_app(pkg)
                else: ok, out = False, "package invalide"
            elif p == "/api/apps":
                ok, out = shell("pm list packages -3")
                return self.send(200, {"ok": ok, "apps": sorted(l[8:] for l in out.splitlines() if l.startswith("package:"))})
            else:
                return self.send(404, {"error": "not found"})
            self.send(200 if ok else 500, {"ok": ok, "out": out})
        except Exception as e:
            self.send(500, {"ok": False, "error": str(e)})

if __name__ == "__main__":
    try:
        _ok, _msg, _rs = update()
        print("mise à jour:", _msg)
        if _rs: restart_soon()
    except Exception as e:
        print("mise à jour impossible:", e)
    print("mode:", MODE, "| connexion:", connect())
    print(f"Ouvre http://<ip-de-la-box>:{PORT} sur ton iPhone")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
