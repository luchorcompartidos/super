/**
 * Góndola · sincronización con Google Sheets (script v0.1.3: agrega la acción "pull" para detectar conflictos)
 * Repo: https://github.com/luchorcompartidos/super
 *
 * Instalación (una sola vez):
 *  1) Cambiá CLAVE por una clave tuya. Es la misma que vas a poner en la app.
 *  2) Elegí la función "preparar" arriba y tocá Ejecutar. Aceptá los permisos.
 *  3) Implementar > Nueva implementación > tipo "Aplicación web":
 *       Ejecutar como: Yo · Quién tiene acceso: Cualquier usuario.
 *     Copiá la URL que termina en /exec y pegala en la app (Datos > Sincronización).
 *  Cuando cambies este código: Implementar > Gestionar implementaciones > editar > Versión nueva.
 */
const CLAVE = 'cambiá-esta-clave';

const TABS = { stores: 'Tiendas', pays: 'MediosPago', prods: 'Productos', pres: 'Presentaciones', prices: 'Precios' };
const FIELDS = {
  stores: ['id', 'name', 'upd'],
  pays:   ['id', 'name', 'pct', 'minimo', 'tope', 'usado', 'dias', 'stores', 'modo', 'upd'],
  prods:  ['id', 'name', 'base', 'upd'],
  pres:   ['id', 'prodId', 'marca', 'desc', 'cont', 'unit', 'pack', 'ean', 'upd'],
  prices: ['id', 'presId', 'storeId', 'precio', 'promo', 'acum', 'fecha', 'hist', 'upd']
};
const TOMBS_TAB = 'Borrados';
const TOMB_FIELDS = ['c', 'id', 'upd'];

function preparar() {
  const ss = SpreadsheetApp.getActive();
  Object.keys(TABS).forEach(c => hoja_(ss, TABS[c], FIELDS[c]));
  hoja_(ss, TOMBS_TAB, TOMB_FIELDS);
  ['Hoja 1', 'Sheet1'].forEach(n => { const h = ss.getSheetByName(n); if (h && h.getLastRow() === 0) ss.deleteSheet(h); });
}

function doGet() {
  return json_({ ok: true, app: 'Góndola', info: 'Sincronización activa. La app se conecta por POST.' });
}

function doPost(e) {
  let req;
  try { req = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'Pedido inválido' }); }
  if (req.token !== CLAVE) return json_({ ok: false, error: 'Clave incorrecta' });
  const ss = SpreadsheetApp.getActive();
  if (req.action === 'ping') return json_({ ok: true, planilla: ss.getName(), script: '0.1.3' });
  if (req.action === 'pull') {
    // Solo lectura: la app compara y te pregunta qué hacer con los conflictos antes de enviar.
    const out = {};
    Object.keys(TABS).forEach(c => { out[c] = leer_(ss, TABS[c], FIELDS[c]); });
    return json_({ ok: true, data: out, tombs: leer_(ss, TOMBS_TAB, TOMB_FIELDS), planilla: ss.getName() });
  }
  if (req.action !== 'sync') return json_({ ok: false, error: 'Acción desconocida' });

  const lock = LockService.getScriptLock();
  lock.waitLock(25000);
  try {
    // Borrados: se guarda la marca más reciente de cada registro
    const tombs = {};
    leer_(ss, TOMBS_TAB, TOMB_FIELDS).forEach(t => { tombs[t.c + '|' + t.id] = t.upd; });
    (req.tombs || []).forEach(t => { const k = t.c + '|' + t.id; if (!tombs[k] || tombs[k] < t.upd) tombs[k] = t.upd; });

    const data = {};
    Object.keys(TABS).forEach(c => {
      const map = {};
      leer_(ss, TABS[c], FIELDS[c]).forEach(r => { map[r.id] = r; });
      // Gana la versión con fecha de modificación más reciente
      ((req.data && req.data[c]) || []).forEach(r => {
        const cur = map[r.id];
        if (!cur || String(cur.upd || '') < String(r.upd || '')) map[r.id] = r;
      });
      Object.keys(map).forEach(id => { const t = tombs[c + '|' + id]; if (t && t >= String(map[id].upd || '')) delete map[id]; });
      data[c] = Object.keys(map).map(id => map[id]);
      escribir_(ss, TABS[c], FIELDS[c], data[c]);
    });
    escribir_(ss, TOMBS_TAB, TOMB_FIELDS, Object.keys(tombs).map(k => { const i = k.indexOf('|'); return { c: k.slice(0, i), id: k.slice(i + 1), upd: tombs[k] }; }));
    // Se devuelven los datos como texto plano (igual que se ven en la planilla)
    const out = {};
    Object.keys(TABS).forEach(c => { out[c] = data[c].map(r => { const o = {}; FIELDS[c].forEach(f => { o[f] = celda_(r[f]); }); return o; }); });
    return json_({ ok: true, data: out, planilla: ss.getName(), time: new Date().toISOString() });
  } finally {
    lock.releaseLock();
  }
}

/* Si editás una fila a mano, se actualiza su fecha de modificación para que la app tome el cambio. */
function onEdit(e) {
  const sh = e.range.getSheet();
  const c = Object.keys(TABS).find(k => TABS[k] === sh.getName());
  if (!c || e.range.getRow() < 2) return;
  const head = sh.getRange(1, 1, 1, sh.getLastColumn()).getDisplayValues()[0];
  const col = head.indexOf('upd') + 1;
  if (!col || (e.range.getNumColumns() === 1 && e.range.getColumn() === col)) return;
  const n = e.range.getNumRows(), t = new Date().toISOString();
  sh.getRange(e.range.getRow(), col, n, 1).setNumberFormat('@').setValues(Array.from({ length: n }, () => [t]));
}

function hoja_(ss, name, fields) {
  let sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  sh.getRange(1, 1, sh.getMaxRows(), fields.length).setNumberFormat('@');
  sh.getRange(1, 1, 1, fields.length).setValues([fields]).setFontWeight('bold');
  sh.setFrozenRows(1);
  return sh;
}
function leer_(ss, name, fields) {
  const sh = ss.getSheetByName(name) || hoja_(ss, name, fields);
  const n = sh.getLastRow() - 1;
  if (n < 1) return [];
  const head = sh.getRange(1, 1, 1, sh.getLastColumn()).getDisplayValues()[0];
  const iid = head.indexOf(fields[0]);
  return sh.getRange(2, 1, n, head.length).getDisplayValues()
    .filter(r => iid >= 0 && r[iid])
    .map(r => { const o = {}; head.forEach((h, i) => { if (h) o[h] = r[i]; }); return o; });
}
function escribir_(ss, name, fields, rows) {
  const sh = hoja_(ss, name, fields);
  const last = sh.getLastRow();
  if (last > 1) sh.getRange(2, 1, last - 1, Math.max(fields.length, sh.getLastColumn())).clearContent();
  if (!rows.length) return;
  sh.getRange(2, 1, rows.length, fields.length).setValues(rows.map(r => fields.map(f => celda_(r[f]))));
}
function celda_(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}
function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
