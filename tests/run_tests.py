#!/usr/bin/env python3
"""Pruebas automáticas del lector de tickets de Góndola.

Carga index.html en Chrome sin ventana, lee cada ticket de tests/tickets/ con el lector de la app
y compara lo leído con tests/esperado.json (productos, cantidades, precios, descuentos, promos y totales).

Uso:  python3 tests/run_tests.py            → compara y sale con error si algo cambió
      python3 tests/run_tests.py --guardar  → guarda el resultado actual como esperado (solo después de revisarlo)
Requiere Python 3 y Google Chrome o Chromium. Los tickets no tienen datos personales.
"""
import html, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, http.server, functools

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
ESPERADO = os.path.join(AQUI, "esperado.json")

PRUEBA_JS = r"""
<pre id="RESULTADO"></pre><script>
(() => {
  const r2 = v => Math.round(v * 100) / 100, out = {};
  try {
    for (const [nombre, texto] of Object.entries(TICKETS)) {
      const t = parseTicket(texto);
      if (t.err) { out[nombre] = { error: t.err }; continue; }
      out[nombre] = {
        cadena: t.chain, sucursal: t.suc, fecha: t.fecha, factura: t.factura, total: r2(t.total), cierra: t.cuadra,
        medio: t.payName || '', descuentoPago: t.payMode || '',
        productos: t.items.map(it => ({ ean: it.ean || (it.peso ? 'peso' : ''), cant: it.qty, precio: r2(it.unit), importe: r2(it.gross),
          descuento: r2(it.discs.reduce((a, d) => a + d.amt, 0)), pago: it.discs.some(d => d.pago), promo: tkPromo(it) }))
      };
    }
    // Leyendas de promos (Precios Claros y tickets)
    out.leyendas = ['2do al 70%', '3x2 hasta 25/11', '2 x $5.000.', '25% OFF', 'Llevando 4 paga 3', '70% de descuento en la segunda unidad']
      .map(l => [l, refPromo({ l1: l, lista: 1000, p1: 0 }).promo]);
  } catch (e) { out.excepcion = String(e && e.stack || e); }
  document.getElementById('RESULTADO').textContent = JSON.stringify(out);
})();
</script></body>"""


def chrome():
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(n)
        if p: return p
    sys.exit("No se encontró Google Chrome o Chromium")


def resultado():
    tickets = {os.path.splitext(f)[0]: open(os.path.join(AQUI, "tickets", f), encoding="utf-8").read()
               for f in sorted(os.listdir(os.path.join(AQUI, "tickets"))) if f.endswith(".txt")}
    app = open(os.path.join(RAIZ, "index.html"), encoding="utf-8").read()
    pagina = app.replace("</body>", "<script>const TICKETS = " + json.dumps(tickets, ensure_ascii=False) + ";</script>" + PRUEBA_JS, 1)
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f: f.write(pagina)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); puerto = s.getsockname()[1]; s.close()
    class Silencioso(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Silencioso, directory=d)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        dom = subprocess.run([chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=5000",
                              "--dump-dom", f"http://127.0.0.1:{puerto}/index.html"], capture_output=True, text=True, timeout=120).stdout
    finally:
        srv.shutdown(); shutil.rmtree(d, ignore_errors=True)
    m = re.search(r'<pre id="RESULTADO">([\s\S]*?)</pre>', dom)
    if not m or not m.group(1).strip(): sys.exit("La página de prueba no devolvió resultados")
    return json.loads(html.unescape(m.group(1)))


def main():
    r = resultado()
    if "excepcion" in r: sys.exit("Error en la app: " + r["excepcion"])
    if "--guardar" in sys.argv:
        with open(ESPERADO, "w", encoding="utf-8") as f: json.dump(r, f, ensure_ascii=False, indent=1)
        print("Guardado", ESPERADO); return
    esp = json.load(open(ESPERADO, encoding="utf-8"))
    fallas = []
    for k in sorted(set(esp) | set(r)):
        if esp.get(k) != r.get(k):
            a, b = esp.get(k), r.get(k)
            if isinstance(a, dict) and isinstance(b, dict):
                for c in sorted(set(a) | set(b)):
                    if c == "productos" and a.get(c) and b.get(c):
                        for i, (x, y) in enumerate(zip(a[c], b[c])):
                            if x != y: fallas.append(f"{k} · producto {i + 1}: esperado {x} · leído {y}")
                        if len(a[c]) != len(b[c]): fallas.append(f"{k} · productos: esperados {len(a[c])} · leídos {len(b[c])}")
                    elif a.get(c) != b.get(c): fallas.append(f"{k} · {c}: esperado {a.get(c)} · leído {b.get(c)}")
            else: fallas.append(f"{k}: esperado {a} · obtenido {b}")
    tot = sum(len(v.get("productos", [])) for k, v in r.items() if isinstance(v, dict))
    if fallas:
        print("FALLAN las pruebas del lector de tickets:"); [print("  - " + f) for f in fallas]; sys.exit(1)
    print(f"OK: {len([k for k in r if k != 'leyendas'])} tickets y {tot} productos leídos como se esperaba; {len(r.get('leyendas', []))} leyendas de promos.")


if __name__ == "__main__":
    main()
