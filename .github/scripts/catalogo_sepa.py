#!/usr/bin/env python3
"""Catálogo y precios de referencia a partir de la base SEPA de Precios Claros (datos.gob.ar).

Descarga el archivo diario más reciente y recorre, para cada comercio, comercio.csv, sucursales.csv
y productos.csv (leyendo de a una fila, sin cargar los archivos enteros en memoria). Escribe:

  <salida>/ean/<5 primeros dígitos>.json   {ean: [descripción, marca, cantidad, unidad]}   (todo el país)
  <salida>/precios/sucursales.json         sucursales de las zonas configuradas
  <salida>/precios/s/<clave>.json          precios y promos de cada una de esas sucursales
  <salida>/meta.json                       fecha, fuente y totales

Las zonas (barrios de CABA y localidades o partidos de PBA) se configuran en .github/catalogo-zonas.txt.
Se generan todas las sucursales de esas zonas: así no queda publicado a cuáles vas vos.
Solo usa la biblioteca estándar de Python.
Variables opcionales: SEPA_URL (zip a usar), SEPA_ZIP (zip ya descargado, para pruebas), ZONAS (archivo de zonas).
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.request, zipfile, collections, datetime

# Portal de origen (CKAN de datos.produccion.gob.ar); datos.gob.ar replica el mismo dataset
CKAN = ["https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios",
        "https://datos.produccion.gob.ar/api/3/action/package_show?id=6f47ec76-d1ce-4e34-a7e1-621fe9b1d0b5",
        "https://datos.gob.ar/api/3/action/package_show?id=produccion-precios-claros---base-sepa"]
PAGINA = "https://datos.produccion.gob.ar/dataset/sepa-precios"
UA = {"User-Agent": "gondola-catalogo/1.1 (+https://github.com/luchorcompartidos/super)"}
csv.field_size_limit(1 << 20)


def ean_ok(code):
    if not re.fullmatch(r"\d{8}|\d{12,13}", code): return False
    d = [int(c) for c in code]; chk = d.pop(); s = 0
    for i, n in enumerate(reversed(d)): s += n * (3 if i % 2 == 0 else 1)
    return (10 - s % 10) % 10 == chk


def fold(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _get(url, timeout=60):
    ultimo = None
    for intento in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r: return r.read()
        except Exception as e:
            ultimo = e; print(f"  {url}: {e}")
            if getattr(e, "code", 0) == 404: break
            time.sleep(5 * (intento + 1))
    raise ultimo


def _fecha(*textos):
    for t in textos:
        m = re.search(r"\d{4}-\d{2}-\d{2}", str(t or ""))
        if m: return m.group(0)
    return ""


def ultimo_zip():
    """Cada día de la semana tiene su archivo (sepa_lunes.zip, …), que se reemplaza con el de esa fecha: se elige el más reciente."""
    if os.environ.get("SEPA_URL"): return os.environ["SEPA_URL"]
    cands = []
    for api in CKAN:
        try: pkg = json.loads(_get(api))["result"]
        except Exception: continue
        for x in pkg.get("resources", []):
            u = str(x.get("url", ""))
            if u.lower().endswith(".zip"):
                cands.append((_fecha(x.get("description"), x.get("name")) or str(x.get("last_modified") or x.get("created") or "")[:10], u, x.get("description") or x.get("name")))
        if cands: break
    if not cands:
        # Sin API: se leen los enlaces de descarga de la página del dataset
        html = _get(PAGINA).decode("utf-8", "replace")
        for m in re.finditer(r'"schema:description":"([^"]*)","schema:encodingFormat":"ZIP","schema:url":"([^"]+\.zip)"', html):
            cands.append((_fecha(m.group(1)), m.group(2), m.group(1)))
        if not cands:
            for u in sorted(set(re.findall(r'https://datos\.produccion\.gob\.ar/dataset/[^"\s]+/download/sepa_[a-z]+\.zip', html))): cands.append(("", u, u))
    cands = [c for c in cands if "sepa" in c[1].lower()] or cands
    if not cands: sys.exit("No se encontraron archivos .zip en el dataset SEPA")
    cands.sort(reverse=True)
    print("Recurso:", cands[0][2], cands[0][0])
    return cands[0][1]


def bajar(url, destino):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=900) as r, open(destino, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)


def num(v):
    v = (v or "").strip().replace(" ", "").replace("$", "")
    if not v: return None
    if "," in v: v = v.replace(".", "").replace(",", ".")
    try: return float(v)
    except ValueError: return None


def precio(v):
    n = num(v)
    if not n or n <= 0: return None
    n = round(n, 2)
    return int(n) if n == int(n) else n


# ---------- zonas ----------
PROV = {"caba": "CABA", "ar c": "CABA", "c": "CABA", "capital federal": "CABA", "ciudad autonoma de buenos aires": "CABA",
        "ciudad de buenos aires": "CABA", "cdad autonoma de buenos aires": "CABA", "pba": "PBA", "ar b": "PBA", "b": "PBA",
        "buenos aires": "PBA", "provincia de buenos aires": "PBA", "bs as": "PBA", "bsas": "PBA"}


def prov_de(v):
    return PROV.get(fold(v), fold(v).upper())


def leer_zonas(path):
    """Cada línea: provincia | zona | otros nombres, separados por coma | códigos postales (solo si falta el barrio)."""
    zonas = []
    if not os.path.exists(path): return zonas
    for linea in open(path, encoding="utf-8"):
        linea = linea.split("#", 1)[0].strip()
        if not linea: continue
        p = [x.strip() for x in linea.split("|")] + ["", "", ""]
        nombres = [p[1]] + [x for x in p[2].split(",") if x.strip()]
        zonas.append({"prov": prov_de(p[0]), "zona": p[1], "nombres": [fold(x) for x in nombres if fold(x)],
                      "cps": set(re.findall(r"\d{4}", p[3]))})
    return zonas


def zona_de(suc, zonas):
    prov = prov_de(suc["provincia"])
    barrio, loc = fold(suc["barrio"]), fold(suc["localidad"])
    cand = [x for x in (barrio, loc) if x]
    for z in zonas:
        if z["prov"] != prov: continue
        for n in z["nombres"]:
            for c in cand:
                if c == n or re.search(r"(^| )" + re.escape(n) + r"( |$)", c): return z["zona"]
    # Si no figura el barrio y la localidad es genérica ("CABA", "Buenos Aires"), se usa el código postal
    m = re.search(r"\d{4}", suc["cp"] or "")
    if m and not barrio and (not loc or loc in PROV):
        for z in zonas:
            if z["prov"] == prov and m.group(0) in z["cps"]: return z["zona"] + " (por código postal)"
    return None


# ---------- lectura de los CSV ----------
def abrir_csv(zf, nombre):
    fh = zf.open(nombre)
    tw = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="")
    primera = tw.readline()
    sep = "|" if primera.count("|") >= primera.count(",") else ","
    cab = [c.strip().lower() for c in next(csv.reader([primera], delimiter=sep))]
    return cab, csv.reader(tw, delimiter=sep)


def idx(cab, *nombres):
    for n in nombres:
        if n in cab: return cab.index(n)
    return None


def val(row, i):
    return (row[i] if i is not None and i < len(row) else "").strip()


def miembro(zf, sufijo, pref=""):
    for n in zf.namelist():
        if n.startswith(pref) and "/" not in n[len(pref):] and n.lower().endswith(sufijo): return n
    return None


class Estado:
    def __init__(self, zonas):
        self.zonas = zonas
        self.cat = collections.defaultdict(collections.Counter)  # catálogo de todo el país
        self.filas = 0
        self.sucs = {}                                            # sucursales de las zonas
        self.precios = collections.defaultdict(dict)             # clave -> {ean: fila}
        self.leyendas = collections.defaultdict(dict)            # clave -> {texto: índice}


def procesar_comercio(zf, E, pref=""):
    """Un paquete sepa (comercio.csv + sucursales.csv + productos.csv)."""
    banderas, fechas = {}, {}
    n = miembro(zf, "comercio.csv", pref)
    if n:
        cab, rd = abrir_csv(zf, n)
        ic, ib, inom, ifec = idx(cab, "id_comercio"), idx(cab, "id_bandera"), idx(cab, "comercio_bandera_nombre"), idx(cab, "comercio_ultima_actualizacion")
        for row in rd:
            k = (val(row, ic), val(row, ib) or "1")
            if not k[0]: continue
            banderas[k] = val(row, inom); fechas[k] = val(row, ifec)[:10]
    mias = {}
    n = miembro(zf, "sucursales.csv", pref)
    if n and E.zonas:
        cab, rd = abrir_csv(zf, n)
        I = {c: idx(cab, c) for c in ("id_comercio", "id_bandera", "id_sucursal", "sucursales_nombre", "sucursales_tipo", "sucursales_calle",
                                         "sucursales_numero", "sucursales_latitud", "sucursales_longitud", "sucursales_barrio",
                                         "sucursales_codigo_postal", "sucursales_localidad", "sucursales_provincia")}
        for row in rd:
            g = lambda c: val(row, I[c])
            com, ban, sid = g("id_comercio"), g("id_bandera") or "1", g("id_sucursal")
            if not com or not sid: continue
            s = {"barrio": g("sucursales_barrio"), "localidad": g("sucursales_localidad"), "provincia": g("sucursales_provincia"), "cp": g("sucursales_codigo_postal")}
            z = zona_de(s, E.zonas)
            if not z: continue
            clave = f"{com}-{ban}-{re.sub(r'[^0-9A-Za-z]+', '_', sid)}"
            dire = " ".join(x for x in (g("sucursales_calle").title(), g("sucursales_numero")) if x)
            lat, lon = num(g("sucursales_latitud")), num(g("sucursales_longitud"))
            info = {"k": clave, "b": banderas.get((com, ban)) or f"Comercio {com}", "n": g("sucursales_nombre"), "d": dire,
                    "ba": s["barrio"].title(), "lo": PROV.get(fold(s["localidad"])) or s["localidad"].title(), "pr": prov_de(s["provincia"]), "cp": s["cp"], "z": z,
                    "t": g("sucursales_tipo"), "f": fechas.get((com, ban), "")}
            if lat and lon: info["ll"] = [round(lat, 5), round(lon, 5)]
            E.sucs[clave] = info; mias[(com, ban, sid)] = clave
    n = miembro(zf, "productos.csv", pref)
    if not n: return
    cab, rd = abrir_csv(zf, n)
    i_com, i_ban, i_suc = idx(cab, "id_comercio"), idx(cab, "id_bandera"), idx(cab, "id_sucursal")
    i_id, i_flag = idx(cab, "id_producto", "productos_ean_codigo"), idx(cab, "productos_ean")
    i_desc, i_marca = idx(cab, "productos_descripcion", "descripcion"), idx(cab, "productos_marca", "marca")
    i_cant, i_uni = idx(cab, "productos_cantidad_presentacion", "cantidad_presentacion"), idx(cab, "productos_unidad_medida_presentacion", "unidad_medida_presentacion")
    i_lista = idx(cab, "productos_precio_lista")
    i_p1, i_l1 = idx(cab, "productos_precio_unitario_promo1"), idx(cab, "productos_leyenda_promo1")
    i_p2, i_l2 = idx(cab, "productos_precio_unitario_promo2"), idx(cab, "productos_leyenda_promo2")
    if i_id is None or i_desc is None: return
    for row in rd:
        ean = re.sub(r"\D", "", val(row, i_id))
        if i_flag is not None and val(row, i_flag) not in ("1", "true", "True", ""): continue
        if not ean_ok(ean) or ean.startswith("00000"): continue   # códigos internos con ceros a la izquierda
        desc = " ".join(val(row, i_desc).split())
        if not desc: continue
        E.cat[ean][(desc, " ".join(val(row, i_marca).split()), num(val(row, i_cant)), val(row, i_uni).lower())] += 1
        E.filas += 1
        if not mias: continue
        clave = mias.get((val(row, i_com), val(row, i_ban) or "1", val(row, i_suc)))
        if not clave: continue
        lista = precio(val(row, i_lista))
        if not lista: continue
        f = [lista]
        ley = E.leyendas[clave]
        for ip, il in ((i_p1, i_l1), (i_p2, i_l2)):
            p, l = precio(val(row, ip)), " ".join(val(row, il).split())[:160]
            if p or l:
                if l and l not in ley: ley[l] = len(ley)
                f += [p or 0, ley[l] if l else -1]
            else:
                f += [0, -1]
        while len(f) > 1 and f[-2:] == [0, -1]: f = f[:-2]
        E.precios[clave][ean] = f


def recorrer(zf, E, prof=0):
    for nombre in zf.namelist():
        if nombre.lower().endswith(".zip") and prof < 3:
            with zipfile.ZipFile(io.BytesIO(zf.read(nombre))) as z2: recorrer(z2, E, prof + 1)
    # Cada carpeta con un productos.csv es un paquete de un comercio
    for pref in sorted({n[: len(n) - len(n.split("/")[-1])] for n in zf.namelist() if n.lower().endswith("productos.csv")}):
        procesar_comercio(zf, E, pref)


def escribir(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":") if indent is None else None, indent=indent)


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "out"
    zonas = leer_zonas(os.environ.get("ZONAS", ".github/catalogo-zonas.txt"))
    print("Zonas:", ", ".join(f"{z['prov']}: {z['zona']}" for z in zonas) or "(ninguna)")
    path, url = os.environ.get("SEPA_ZIP"), "local"
    if not path:
        url = ultimo_zip(); path = "/tmp/sepa.zip"; print("Descargando", url); bajar(url, path)
    E = Estado(zonas)
    with zipfile.ZipFile(path) as zf: recorrer(zf, E)
    if not E.cat: sys.exit("No se encontraron productos con código de barras válido")
    shards = collections.defaultdict(dict)
    for ean, c in E.cat.items():
        (desc, marca, cant, uni), _ = c.most_common(1)[0]   # la descripción más repetida entre comercios
        shards[ean[:5]][ean] = [desc, marca, cant, uni]
    for k, v in shards.items(): escribir(os.path.join(salida, "ean", k + ".json"), v)
    hoy = datetime.date.today().isoformat()
    sucs = []
    for clave, info in sorted(E.sucs.items(), key=lambda kv: (kv[1]["z"], kv[1]["b"], kv[1]["n"])):
        p = E.precios.get(clave)
        info["np"] = len(p or {})
        sucs.append(info)
        if p:
            ley = sorted(E.leyendas[clave].items(), key=lambda kv: kv[1])
            escribir(os.path.join(salida, "precios", "s", clave + ".json"),
                     {"k": clave, "f": info["f"] or hoy, "i": [info["b"], info["n"], info["d"], info["z"]], "l": [t for t, _ in ley], "p": p})
    escribir(os.path.join(salida, "precios", "sucursales.json"), {"fecha": hoy, "zonas": [f"{z['prov']}: {z['zona']}" for z in zonas], "s": sucs})
    meta = {"fecha": hoy, "fuente": "Precios Claros - SEPA (datos.produccion.gob.ar)", "recurso": url, "productos": len(E.cat), "filas": E.filas,
            "archivos": len(shards), "zonas": len(zonas), "sucursales": len(sucs), "sucursales_con_precios": sum(1 for s in sucs if s["np"])}
    escribir(os.path.join(salida, "meta.json"), meta, indent=1)
    with open(os.path.join(salida, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Catálogo SEPA para Góndola\n\nGenerado automáticamente por `.github/workflows/catalogo-sepa.yml` (rama main). "
                "Fuente: Precios Claros - SEPA, datos.gob.ar. Incluye el catálogo por código de barras de todo el país y "
                "los precios informados por todas las sucursales de las zonas de `.github/catalogo-zonas.txt`. "
                "Esta rama se reemplaza en cada actualización.\n")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
