#!/usr/bin/env python3
"""Góndola · Actualizar el catálogo y los precios de Precios Claros desde tu computadora.

El portal del Gobierno no deja descargar la base SEPA desde los servidores de GitHub, así que la descarga
y el proceso se hacen acá, con tu conexión. Después se sube un único archivo comprimido a GitHub y un flujo
de GitHub lo publica en la rama "catalogo", que es la que lee la app.

Uso:  doble clic en "Actualizar catalogo.bat"  (o:  py -3 gondola_catalogo.py)
      --auto  modo programado: sin preguntas, todo queda en registro.txt
Requiere solo Python 3.9 o más nuevo (biblioteca estándar). Antes de cada corrida se actualiza solo.
"""
import base64, ctypes, datetime, importlib.util, json, os, shutil, sys, time, traceback, urllib.error, urllib.request, zipfile

VERSION = "1.0"
REPO = "luchorcompartidos/super"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/"
API = f"https://api.github.com/repos/{REPO}"
RAMA_SUBIDA = os.environ.get("GONDOLA_RAMA_SUBIDA", "catalogo-subida")
FLUJO = "catalogo-publicar.yml"
AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = os.path.join(AQUI, "motor")
TRABAJO = os.path.join(AQUI, "trabajo")
CONF = os.path.join(AQUI, "config.txt")
LOG = os.path.join(AQUI, "registro.txt")
AUTO = "--auto" in sys.argv
LIBRE_MIN_GB = 4          # espacio libre mínimo en el disco de esta carpeta
MAX_SUBIDA_MB = 70        # GitHub acepta hasta 100 MB por archivo (en base64 crece un tercio)


# ---------- registro ----------
class Tee:
    def __init__(self, *fs): self.fs = [f for f in fs if f]
    def write(self, t):
        for f in self.fs:
            try: f.write(t); f.flush()
            except Exception: pass
    def flush(self): pass


def abrir_registro():
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1_000_000:   # se conserva la última parte
            with open(LOG, encoding="utf-8", errors="replace") as f: resto = f.read()[-300_000:]
            with open(LOG, "w", encoding="utf-8") as f: f.write(resto)
        f = open(LOG, "a", encoding="utf-8")
    except Exception:
        f = None
    sys.stdout = Tee(sys.__stdout__, f)
    sys.stderr = Tee(sys.__stderr__, f)


def log(*a):
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *a)


# ---------- prioridad baja: tus programas tienen preferencia ----------
def prioridad_baja():
    try:
        if os.name == "nt":
            k = ctypes.windll.kernel32; h = k.GetCurrentProcess()
            # Modo "segundo plano": baja la prioridad de CPU, de disco y de memoria
            if not k.SetPriorityClass(h, 0x00100000): k.SetPriorityClass(h, 0x00004000)
        else:
            os.nice(10)
    except Exception:
        pass


# ---------- configuración (token de GitHub) ----------
def leer_conf():
    c = {}
    if os.path.exists(CONF):
        for linea in open(CONF, encoding="utf-8-sig"):
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1); c[k.strip().upper()] = v.strip()
    return c


def gh(metodo, ruta, token, cuerpo=None, timeout=120):
    data = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(ruta if ruta.startswith("http") else API + ruta, data=data, method=metodo, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gondola-catalogo/" + VERSION})
    if data: req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        t = r.read()
        return json.loads(t) if t else {}


def detalle(e):
    if isinstance(e, urllib.error.HTTPError):
        try: return f"HTTP {e.code}: {json.loads(e.read()).get('message', '')}"
        except Exception: return f"HTTP {e.code}"
    return str(e)


def token_valido(token):
    try: gh("GET", "", token, timeout=30); return True
    except Exception as e: log("El token no funciona:", detalle(e)); return False


def obtener_token():
    t = leer_conf().get("TOKEN", "")
    if t and token_valido(t): return t
    if AUTO:
        log("Falta un token válido en config.txt. Corré una vez 'Actualizar catalogo.bat' a mano para cargarlo.")
        sys.exit(2)
    print("\nPara publicar los datos hace falta un token de GitHub (se pide una sola vez).")
    print("Crealo en: https://github.com/settings/personal-access-tokens/new")
    print("  - Repository access: Only select repositories -> super")
    print("  - Permissions: Contents = Read and write · Actions = Read and write")
    while True:
        t = input("\nPegá el token (clic derecho para pegar) y tocá Enter: ").strip()
        if t and token_valido(t): break
        print("No funcionó. Revisá que esté completo y con los permisos indicados.")
    with open(CONF, "w", encoding="utf-8") as f:
        f.write("# Token de GitHub de Góndola (no lo compartas)\nTOKEN=" + t + "\n")
    log("Token guardado en config.txt")
    return t


# ---------- se actualiza solo desde el repo ----------
def bajar_texto(url):
    req = urllib.request.Request(url + "?t=" + str(int(time.time())), headers={"User-Agent": "gondola-catalogo/" + VERSION})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()


def actualizar_archivos():
    os.makedirs(MOTOR, exist_ok=True)
    for remoto, local in ((".github/scripts/catalogo_sepa.py", os.path.join(MOTOR, "catalogo_sepa.py")),
                          (".github/catalogo-zonas.txt", os.path.join(MOTOR, "catalogo-zonas.txt")),
                          ("local/gondola_catalogo.py", os.path.abspath(__file__))):
        try:
            nuevo = bajar_texto(RAW + remoto)
            viejo = open(local, "rb").read() if os.path.exists(local) else b""
            if nuevo != viejo:
                with open(local + ".nuevo", "wb") as f: f.write(nuevo)
                os.replace(local + ".nuevo", local)
                log("Actualizado:", os.path.basename(local) + (" (se usa desde la próxima vez)" if local == os.path.abspath(__file__) else ""))
        except Exception as e:
            if not os.path.exists(local): raise RuntimeError(f"No se pudo descargar {remoto}: {detalle(e)}")
            log(f"No se pudo actualizar {os.path.basename(local)} ({detalle(e)}); se usa la copia que ya está.")


def cargar_motor():
    spec = importlib.util.spec_from_file_location("catalogo_sepa", os.path.join(MOTOR, "catalogo_sepa.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


# ---------- descarga ----------
def libre_gb(ruta):
    return shutil.disk_usage(ruta).free / 1e9


def descargar(mod, url, destino):
    for intento in range(3):
        try:
            req = urllib.request.Request(url, headers=mod.UA)
            with urllib.request.urlopen(req, timeout=300) as r, open(destino, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                if total:
                    log(f"Tamaño del archivo: {total / 1e6:,.0f} MB")
                    if libre_gb(AQUI) < total * 3 / 1e9 + 1:
                        raise RuntimeError(f"No alcanza el espacio en disco: hacen falta unos {total * 3 / 1e9 + 1:.1f} GB libres")
                hecho, aviso = 0, 0
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b); hecho += len(b)
                    if total and hecho * 10 // total > aviso:
                        aviso = hecho * 10 // total; log(f"Descargado {aviso * 10}%")
            return
        except RuntimeError:
            raise
        except Exception as e:
            log(f"Falló la descarga ({detalle(e)}), intento {intento + 1} de 3")
            time.sleep(20 * (intento + 1))
    raise RuntimeError("No se pudo descargar la base SEPA")


# ---------- subida y publicación ----------
def subir(token, archivo):
    log("Subiendo a GitHub…")
    with open(archivo, "rb") as f: b64 = base64.b64encode(f.read()).decode()
    blob = gh("POST", "/git/blobs", token, {"content": b64, "encoding": "base64"}, timeout=1800); del b64
    tree = gh("POST", "/git/trees", token, {"tree": [{"path": "catalogo.zip", "mode": "100644", "type": "blob", "sha": blob["sha"]}]})
    com = gh("POST", "/git/commits", token, {"message": f"Datos SEPA {datetime.date.today().isoformat()} (desde la computadora)", "tree": tree["sha"], "parents": []})
    try:
        gh("PATCH", "/git/refs/heads/" + RAMA_SUBIDA, token, {"sha": com["sha"], "force": True})
    except urllib.error.HTTPError as e:
        if e.code not in (404, 422): raise
        gh("POST", "/git/refs", token, {"ref": "refs/heads/" + RAMA_SUBIDA, "sha": com["sha"]})


def publicar(token):
    desde = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    gh("POST", f"/actions/workflows/{FLUJO}/dispatches", token, {"ref": "main", "inputs": {"origen": RAMA_SUBIDA, "destino": os.environ.get("GONDOLA_DESTINO", "catalogo")}})
    log("Publicando en GitHub (tarda unos minutos)…")
    run = None
    for _ in range(90):                 # hasta 15 minutos
        time.sleep(10)
        try: runs = gh("GET", f"/actions/workflows/{FLUJO}/runs?event=workflow_dispatch&per_page=5", token).get("workflow_runs", [])
        except Exception: continue
        runs = [r for r in runs if datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= desde]
        if runs:
            run = runs[0]
            if run["status"] == "completed": break
    if not run: log("No se pudo confirmar la publicación: revisá Actions en GitHub."); return False
    if run["status"] != "completed": log("La publicación sigue en curso:", run["html_url"]); return True
    if run["conclusion"] == "success": log("Publicado. La app toma los datos nuevos la próxima vez que se abra con conexión."); return True
    log("La publicación falló:", run["html_url"]); return False


# ---------- principal ----------
def principal():
    log(f"=== Góndola · actualizar catálogo (v{VERSION}{', programado' if AUTO else ''}) ===")
    prioridad_baja()
    token = obtener_token()
    actualizar_archivos()
    mod = cargar_motor()
    if libre_gb(AQUI) < LIBRE_MIN_GB:
        raise RuntimeError(f"Hay {libre_gb(AQUI):.1f} GB libres en el disco: hacen falta al menos {LIBRE_MIN_GB} GB")
    shutil.rmtree(TRABAJO, ignore_errors=True); os.makedirs(TRABAJO)
    os.environ["TMP"] = os.environ["TEMP"] = os.environ["TMPDIR"] = TRABAJO
    import tempfile; tempfile.tempdir = TRABAJO
    try:
        url = mod.ultimo_zip()
        zp = os.path.join(TRABAJO, "sepa.zip")
        log("Descargando", url); descargar(mod, url, zp)
        out = os.path.join(TRABAJO, "out")
        os.environ["SEPA_ZIP"] = zp; os.environ["ZONAS"] = os.path.join(MOTOR, "catalogo-zonas.txt")
        log("Procesando (puede tardar entre 10 y 30 minutos)…")
        argv = sys.argv; sys.argv = [argv[0], out]
        try: mod.main()
        finally: sys.argv = argv
        os.remove(zp)
        paquete = os.path.join(TRABAJO, "catalogo.zip")
        with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for raiz, _, archivos in os.walk(out):
                for a in archivos:
                    p = os.path.join(raiz, a); z.write(p, os.path.relpath(p, out).replace(os.sep, "/"))
        mb = os.path.getsize(paquete) / 1e6
        log(f"Paquete listo: {mb:.1f} MB")
        if mb > MAX_SUBIDA_MB:
            raise RuntimeError(f"El paquete pesa {mb:.0f} MB y el máximo es {MAX_SUBIDA_MB} MB: conviene achicar las zonas")
        subir(token, paquete)
        return 0 if publicar(token) else 1
    finally:
        shutil.rmtree(TRABAJO, ignore_errors=True)


if __name__ == "__main__":
    abrir_registro()
    codigo = 1
    try:
        codigo = principal()
    except SystemExit as e:
        codigo = e.code if isinstance(e.code, int) else 1
        if e.code not in (0, None) and not isinstance(e.code, int): log("Error:", e.code)
    except KeyboardInterrupt:
        log("Cancelado."); codigo = 1
    except Exception as e:
        log("Error:", detalle(e)); traceback.print_exc()
    log("Terminó " + ("bien." if codigo == 0 else "con errores (detalle arriba)."))
    sys.exit(codigo)
