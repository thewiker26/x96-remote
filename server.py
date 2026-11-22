#!/usr/bin/env python3
"""Relais X96 Remote : sert la page web et traduit les boutons en commandes ADB.
Aucune dépendance obligatoire.
Variables : ADB_TARGET (def. localhost:5555), PORT (def. 8080), ADB (def. adb),
            X96_PIN (code facultatif demandé par la page), ADB_MODE (bin|py)."""
import json, os, re, shlex, subprocess, sys, threading, time, unicodedata
import urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ADB = os.environ.get("ADB", "adb")
TARGET = os.environ.get("ADB_TARGET", "localhost:5555")
PORT = int(os.environ.get("PORT", "8080"))
PIN = os.environ.get("X96_PIN", "")
HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
IPTV = os.environ.get("IPTV_BASE", "https://iptv-org.github.io/iptv/")

KEYS = {"up": 19, "down": 20, "left": 21, "right": 22, "ok": 23, "back": 4, "home": 3,
        "menu": 82, "power": 26, "sleep": 223, "wake": 224, "volup": 24, "voldown": 25,
        "mute": 164, "play": 85, "ff": 90, "rw": 89, "next": 87, "prev": 88,
        "chup": 166, "chdown": 167, "info": 165, "del": 67, "enter": 66, "search": 84,
        "recent": 187, "tab": 61, **{str(i): 7 + i for i in range(10)}}
APPS = {"settings": "am start -a android.settings.SETTINGS",
        "wifi": "am start -a android.settings.WIFI_SETTINGS",
        "display": "am start -a android.settings.DISPLAY_SETTINGS",
        "sound": "am start -a android.settings.SOUND_SETTINGS",
        "bluetooth": "am start -a android.settings.BLUETOOTH_SETTINGS"}

# ---------------------------------------------------------------- ADB

def _bin_ok():
    try:
        return subprocess.run([ADB, "version"], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False

# Mode "bin" : programme adb. Mode "py" : ADB en Python pur (paquet adb-shell), si adb ne démarre pas.
MODE = os.environ.get("ADB_MODE") or ("bin" if _bin_ok() else "py")
_dev = None
_lock = threading.Lock()

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
    try:
        if MODE == "py":
            return _dev is not None and _dev.available
        p = subprocess.run([ADB, "-s", TARGET, "get-state"], capture_output=True, text=True, timeout=10)
        return p.returncode == 0 and "device" in p.stdout
    except Exception:
        return False

def _run(cmd):
    if MODE == "py":
        with _lock:
            if _dev is None or not _dev.available:
                ok, out = connect()
                if not ok:
                    return False, out
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

# ---------------------------------------------------------------- Actions

def keys(name, count=1):
    code = KEYS.get(name)
    if code is None:
        return False, "touche inconnue"
    count = max(1, min(int(count), 60))
    return shell("input keyevent " + " ".join([str(code)] * count))

def clean_text(t):
    """input text ne gère que l'ASCII : accents retirés, caractères exotiques ignorés."""
    t = unicodedata.normalize("NFKD", str(t))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("“", '"').replace("”", '"')
    return "".join(c for c in t if " " <= c <= "~" and c != "%")[:300]

def send_text(t):
    t = clean_text(t)
    if not t:
        return True, ""
    return shell("input text " + shlex.quote(t.replace(" ", "%s")))

_size = None
def screen_size():
    global _size
    if _size:
        return _size
    ok, out = shell("wm size")
    m = re.findall(r"(\d{3,5})x(\d{3,5})", out if ok else "")
    _size = (int(m[-1][0]), int(m[-1][1])) if m else (1920, 1080)
    return _size

def _frac(v):
    return max(0.0, min(1.0, float(v)))

def tap(x, y):
    w, h = screen_size()
    return shell(f"input tap {int(_frac(x) * (w - 1))} {int(_frac(y) * (h - 1))}")

def swipe(x1, y1, x2, y2, ms=300):
    w, h = screen_size()
    p = [int(_frac(x1) * (w - 1)), int(_frac(y1) * (h - 1)), int(_frac(x2) * (w - 1)), int(_frac(y2) * (h - 1))]
    return shell("input swipe %d %d %d %d %d" % (*p, max(50, min(int(ms), 1500))))

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

# ---------------------------------------------------------------- Mise à jour

def _git(*a):
    p = subprocess.run(["git", "-C", HERE, *a], capture_output=True, text=True, timeout=60)
    return p.returncode == 0, (p.stdout + p.stderr).strip()

def version():
    ok, out = _git("rev-parse", "--short", "HEAD")
    return out if ok else "?"

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
    threading.Timer(1.0, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()

# ---------------------------------------------------------------- Chaînes iptv-org

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
            meta = {"name": name, "logo": g("tvg-logo"), "group": g("group-title"), "id": g("tvg-id")}
        elif line and not line.startswith("#") and meta:
            meta["url"] = line
            out.append(meta)
            meta = None
    return out

FOOT = re.compile(r"foot|soccer|f[uú]tbol|calcio|ligue|liga|premier|champions|uefa|fifa|bein|dazn|bundesliga|sport ?5|sport ?1|one sport|eleven|sky sport|canal\+? ?sport|rmc|eurosport|arena|supersport|\bsport", re.I)
CATEGORIES = {"news", "kids", "movies", "music", "sports", "documentary", "entertainment", "general", "series", "comedy", "culture", "religious"}

def channels(country, category, q, limit, mode=""):
    country = (country or "").lower()
    if mode in ("foot", "sport"):
        items = parse_m3u(fetch(IPTV + "categories/sports.m3u"))
        if country:
            try:
                items += parse_m3u(fetch(IPTV + f"countries/{country}.m3u"))
            except Exception:
                pass
        if mode == "foot":
            items = [c for c in items if FOOT.search(c["name"])]
    elif mode in CATEGORIES:
        items = parse_m3u(fetch(IPTV + f"categories/{mode}.m3u"))
        if country:
            rx = re.compile(r"\.%s(@|$)" % re.escape(country), re.I)
            items = [c for c in items if rx.search(c.get("id", ""))]
    else:
        src = f"categories/{category}.m3u" if category else f"countries/{country or 'fr'}.m3u"
        items = parse_m3u(fetch(IPTV + src))
    seen, out = set(), []
    for c in items:
        if c["url"] not in seen:
            seen.add(c["url"])
            out.append(c)
    q = (q or "").lower()
    if q:
        out = [c for c in out if q in c["name"].lower()]
    return out[:limit]

_alive = {}
def check_url(u):
    c = _alive.get(u)
    if c and time.time() - c[0] < 1800:
        return c[1]
    ok = False
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-1023"})
        with urllib.request.urlopen(req, timeout=5) as r:
            head = r.read(1024)
            ok = r.status in (200, 206) and (b"#EXTM3U" in head if u.split("?")[0].endswith(".m3u8") else True)
    except Exception:
        ok = False
    _alive[u] = (time.time(), ok)
    return ok

def check_many(urls):
    urls = [u for u in urls if isinstance(u, str) and re.match(r"^https?://", u)][:30]
    with ThreadPoolExecutor(10) as ex:
        return dict(zip(urls, ex.map(check_url, urls)))

# ---------------------------------------------------------------- Liste de chaînes pour Kodi (sans iPhone)

DEFAULT_COUNTRIES = [c for c in re.split(r"[ ,]+", os.environ.get("X96_COUNTRIES", "fr,il").lower()) if re.match(r"^[a-z]{2}$", c)]
_dead = {}          # url -> heure à laquelle elle a été vue morte
_warming = False

def _is_dead(u):
    t = _dead.get(u)
    return bool(t) and time.time() - t < 12 * 3600

def warm(urls):
    """Teste les flux en arrière-plan. Les listes suivantes cachent ceux qui ne répondent pas."""
    global _warming
    if _warming:
        return
    _warming = True
    def run():
        global _warming
        try:
            res = {}
            with ThreadPoolExecutor(10) as ex:
                for u, ok in zip(urls, ex.map(check_url, urls)):
                    res[u] = ok
            bad = [u for u, ok in res.items() if not ok]
            if len(res) >= 10 and len(bad) > 0.9 * len(res):
                return          # probablement un problème de réseau, on ne cache rien
            now = time.time()
            for u, ok in res.items():
                if ok:
                    _dead.pop(u, None)
                else:
                    _dead[u] = now
        finally:
            _warming = False
    threading.Thread(target=run, daemon=True).start()

def build_playlist(countries, foot=True, only_foot=False, alive=True):
    countries = [c for c in countries if re.match(r"^[a-z]{2}$", c)][:6] or DEFAULT_COUNTRIES
    items = []
    for cc in countries:
        try:
            lst = parse_m3u(fetch(IPTV + f"countries/{cc}.m3u"))
        except Exception:
            continue
        for c in lst:
            c = dict(c)
            g = c.get("group") or "Autres"
            c["group"] = f"{cc.upper()} · {g}" if len(countries) > 1 else g
            items.append(c)
    if foot:
        rx = re.compile(r"\.(%s)(@|$)" % "|".join(map(re.escape, countries)), re.I)
        try:
            items += [dict(c) for c in parse_m3u(fetch(IPTV + "categories/sports.m3u")) if rx.search(c.get("id", ""))]
        except Exception:
            pass
    seen, out = set(), []
    for c in items:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        if foot and FOOT.search(c["name"]):
            c["group"] = "Foot"
        elif only_foot:
            continue
        out.append(c)
    if alive:
        warm([c["url"] for c in out if c["url"] not in _alive][:600])
        out = [c for c in out if not _is_dead(c["url"])]
    out.sort(key=lambda c: (c["group"] != "Foot", c["group"], c["name"].lower()))
    q = lambda s: str(s).replace('"', "'").replace("\n", " ")
    lines = ["#EXTM3U"]
    for c in out:
        lines.append('#EXTINF:-1 tvg-id="%s" tvg-logo="%s" group-title="%s",%s' % (q(c.get("id", "")), q(c.get("logo", "")), q(c["group"]), q(c["name"])))
        lines.append(c["url"])
    return "\n".join(lines) + "\n"

def playlist_for(path, q):
    name = path[1:-4]
    if name == "mix":
        args = dict(countries=DEFAULT_COUNTRIES, foot=True, only_foot=False)
    elif name == "foot":
        args = dict(countries=DEFAULT_COUNTRIES, foot=True, only_foot=True)
    elif name == "playlist":
        cs = [c for c in re.split(r"[ ,]+", q.get("country", "").lower()) if c]
        args = dict(countries=cs or DEFAULT_COUNTRIES, foot=q.get("foot", "1") == "1", only_foot=q.get("only", "0") == "1")
    else:
        args = dict(countries=[name], foot=q.get("foot", "0") == "1", only_foot=False)
    return build_playlist(alive=q.get("alive", "1") != "0", **args)

# ---------------------------------------------------------------- HTTP

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

    def authorized(self):
        return not PIN or self.headers.get("X-Pin", "") == PIN

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}
        if u.path == "/playlist.m3u" or re.match(r"^/(mix|foot|[a-z]{2})\.m3u$", u.path):
            try:
                body = playlist_for(u.path, q).encode("utf-8")
            except Exception as e:
                return self.send(502, {"ok": False, "error": str(e)})
            return self.send(200, body, "audio/x-mpegurl; charset=utf-8")
        try:
            if u.path == "/api/status":
                return self.send(200, {"connected": is_connected(), "target": TARGET, "mode": MODE,
                                       "version": VERSION, "pin_required": bool(PIN), "authorized": self.authorized()})
            if u.path == "/api/channels":
                if not self.authorized():
                    return self.send(401, {"ok": False, "error": "pin"})
                items = channels(q.get("country", "fr"), q.get("category", ""), q.get("q", ""),
                                 int(q.get("limit", "300")), q.get("mode", ""))
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
        global VERSION
        n = int(self.headers.get("Content-Length") or 0)
        try:
            if not self.authorized():
                return self.send(401, {"ok": False, "error": "pin"})
            d = json.loads(self.rfile.read(n) or b"{}")
            p = self.path
            if p == "/api/connect":
                ok, out = connect()
            elif p == "/api/update":
                ok, out, rs = update()
                VERSION = version()
                if rs:
                    restart_soon()
                return self.send(200 if ok else 500, {"ok": ok, "out": out, "restart": rs, "version": VERSION})
            elif p == "/api/key":
                ok, out = keys(d.get("key"), d.get("count", 1))
                if not ok and out == "touche inconnue":
                    return self.send(400, {"ok": False, "error": out})
            elif p == "/api/text":
                ok, out = send_text(d.get("text", ""))
            elif p == "/api/tap":
                ok, out = tap(d.get("x", .5), d.get("y", .5))
            elif p == "/api/swipe":
                ok, out = swipe(d.get("x1", .5), d.get("y1", .5), d.get("x2", .5), d.get("y2", .5), d.get("ms", 300))
            elif p == "/api/open":
                ok, out = open_stream(str(d.get("url", "")), str(d.get("package", "")))
            elif p == "/api/launch":
                pkg = str(d.get("package", ""))
                if pkg in APPS:
                    ok, out = shell(APPS[pkg])
                elif re.match(r"^[A-Za-z0-9_.]+$", pkg):
                    ok, out = launch_app(pkg)
                else:
                    ok, out = False, "package invalide"
            elif p == "/api/apps":
                ok, out = shell("pm list packages -3")
                return self.send(200, {"ok": ok, "apps": sorted(l[8:] for l in out.splitlines() if l.startswith("package:"))})
            elif p == "/api/check":
                return self.send(200, {"ok": True, "alive": check_many(d.get("urls", []))})
            else:
                return self.send(404, {"error": "not found"})
            self.send(200 if ok else 500, {"ok": ok, "out": out})
        except Exception as e:
            self.send(500, {"ok": False, "error": str(e)})

VERSION = version()

def prewarm():
    """Au démarrage : prépare la liste pour Kodi (teste les flux), en réessayant tant que le réseau n'est pas prêt."""
    for _ in range(12):
        try:
            if any(l.startswith("http") for l in build_playlist(DEFAULT_COUNTRIES).splitlines()):
                return
        except Exception:
            pass
        time.sleep(30)

def keep_connected():
    """Se reconnecte seul à la box (utile au démarrage, quand l'ADB met du temps à être prêt)."""
    while True:
        try:
            if not is_connected():
                connect()
        except Exception:
            pass
        time.sleep(10)

if __name__ == "__main__":
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    except OSError:
        print(f"Le relais tourne déjà sur le port {PORT}. Rien à faire.")
        sys.exit(0)
    try:
        _ok, _msg, _rs = update()
        print("mise à jour:", _msg)
        if _rs:
            restart_soon()
    except Exception as e:
        print("mise à jour impossible:", e)
    VERSION = version()
    print("mode:", MODE, "| connexion:", connect(), "| version:", VERSION, "| PIN:", "oui" if PIN else "non")
    print(f"Ouvre http://<ip-de-la-box>:{PORT} sur ton iPhone")
    threading.Thread(target=keep_connected, daemon=True).start()
    threading.Thread(target=prewarm, daemon=True).start()
    srv.serve_forever()
