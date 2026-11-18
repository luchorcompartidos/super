#!/usr/bin/env python3
"""Catálogo de productos por código de barras a partir de la base SEPA de Precios Claros (datos.gob.ar).

Descarga el archivo diario más reciente, recorre los productos.csv de cada comercio y escribe
<salida>/ean/<5 primeros dígitos>.json  ->  {ean: [descripción, marca, cantidad, unidad]}
y <salida>/meta.json con la fecha y la fuente. Solo usa la biblioteca estándar de Python.
Variables opcionales: SEPA_URL (zip a usar), SEPA_ZIP (zip ya descargado, para pruebas).
"""
import csv, io, json, os, sys, urllib.request, zipfile, collections, datetime, re

CKAN = "https://datos.gob.ar/api/3/action/package_show?id=produccion-precios-claros---base-sepa"
UA = {"User-Agent": "gondola-catalogo/1.0 (+https://github.com/luchorcompartidos/super)"}

def ean_ok(code):
    if not re.fullmatch(r"\d{8}|\d{12,13}", code): return False
    d = [int(c) for c in code]; chk = d.pop(); s = 0
    for i, n in enumerate(reversed(d)): s += n * (3 if i % 2 == 0 else 1)
    return (10 - s % 10) % 10 == chk

def ultimo_zip():
    if os.environ.get("SEPA_URL"): return os.environ["SEPA_URL"]
    with urllib.request.urlopen(urllib.request.Request(CKAN, headers=UA), timeout=60) as r:
        pkg = json.load(r)["result"]
    res = [x for x in pkg["resources"] if str(x.get("url", "")).lower().endswith(".zip")]
    if not res: sys.exit("No se encontraron archivos .zip en el dataset SEPA")
    res.sort(key=lambda x: x.get("last_modified") or x.get("created") or "", reverse=True)
    print("Recurso:", res[0].get("name"), res[0].get("last_modified") or res[0].get("created"))
    return res[0]["url"]

def bajar(url, destino):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(destino, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)

def num(v):
    v = (v or "").strip().replace(" ", "")
    if not v: return None
    if "," in v: v = v.replace(".", "").replace(",", ".")
    try: return float(v)
    except ValueError: return None

def leer_productos(data, acum):
    texto = data.decode("utf-8-sig", errors="replace")
    primera = texto.split("\n", 1)[0]
    sep = "|" if primera.count("|") >= primera.count(",") else ","
    rd = csv.DictReader(io.StringIO(texto), delimiter=sep)
    campos = {c.lower().strip(): c for c in (rd.fieldnames or [])}
    def col(*nombres):
        for n in nombres:
            if n in campos: return campos[n]
        return None
    c_id, c_flag = col("id_producto", "productos_ean_codigo"), col("productos_ean")
    c_desc, c_marca = col("productos_descripcion", "descripcion"), col("productos_marca", "marca")
    c_cant, c_uni = col("productos_cantidad_presentacion", "cantidad_presentacion"), col("productos_unidad_medida_presentacion", "unidad_medida_presentacion")
    if not c_id or not c_desc: return 0
    n = 0
    for row in rd:
        ean = re.sub(r"\D", "", row.get(c_id) or "")
        if c_flag and (row.get(c_flag) or "").strip() not in ("1", "true", "True", ""): continue
        if not ean_ok(ean): continue
        desc = " ".join((row.get(c_desc) or "").split())
        if not desc: continue
        clave = (desc, " ".join((row.get(c_marca) or "").split()), num(row.get(c_cant) if c_cant else None), (row.get(c_uni) or "").strip().lower() if c_uni else "")
        acum[ean][clave] += 1; n += 1
    return n

def recorrer(zf, acum, prof=0):
    total = 0
    for nombre in zf.namelist():
        low = nombre.lower()
        if low.endswith(".zip") and prof < 3:
            with zipfile.ZipFile(io.BytesIO(zf.read(nombre))) as z2: total += recorrer(z2, acum, prof + 1)
        elif low.endswith("productos.csv"):
            total += leer_productos(zf.read(nombre), acum)
    return total

def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "out"
    path = os.environ.get("SEPA_ZIP")
    url = "local"
    if not path:
        url = ultimo_zip(); path = "/tmp/sepa.zip"; print("Descargando", url); bajar(url, path)
    acum = collections.defaultdict(collections.Counter)
    with zipfile.ZipFile(path) as zf: filas = recorrer(zf, acum)
    if not acum: sys.exit("No se encontraron productos con código de barras válido")
    shards = collections.defaultdict(dict)
    for ean, c in acum.items():
        (desc, marca, cant, uni), _ = c.most_common(1)[0]   # la descripción más repetida entre comercios
        shards[ean[:5]][ean] = [desc, marca, cant, uni]
    os.makedirs(os.path.join(salida, "ean"), exist_ok=True)
    for k, v in shards.items():
        with open(os.path.join(salida, "ean", k + ".json"), "w", encoding="utf-8") as f: json.dump(v, f, ensure_ascii=False, separators=(",", ":"))
    meta = {"fecha": datetime.date.today().isoformat(), "fuente": "Precios Claros - SEPA (datos.gob.ar)", "recurso": url, "productos": len(acum), "filas": filas, "archivos": len(shards)}
    with open(os.path.join(salida, "meta.json"), "w", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=1)
    with open(os.path.join(salida, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Catálogo SEPA para Góndola\n\nGenerado automáticamente por `.github/workflows/catalogo-sepa.yml` (rama main). "
                "Fuente: Precios Claros - SEPA, datos.gob.ar. Esta rama se reemplaza en cada actualización.\n")
    print(json.dumps(meta, ensure_ascii=False))

if __name__ == "__main__":
    main()
