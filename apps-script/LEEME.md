# Sincronización de Góndola con Google Sheets

1. Creá una planilla nueva en Google Sheets (por ejemplo "Góndola datos").
2. En la planilla: **Extensiones → Apps Script**. Borrá lo que haya y pegá el contenido de `Codigo.gs`.
3. En la línea `const CLAVE = 'cambiá-esta-clave';` poné una clave tuya. Guardá.
4. Elegí la función **preparar** y tocá **Ejecutar**. Aceptá los permisos (es tu propia cuenta).
   Se crean las pestañas Tiendas, MediosPago, Productos, Presentaciones, Precios y Borrados.
5. **Implementar → Nueva implementación → Aplicación web**.
   Ejecutar como: **Yo**. Quién tiene acceso: **Cualquier usuario**. Copiá la URL que termina en `/exec`.
6. En la app: **Datos → Sincronización**, pegá la URL y la clave, tocá **Probar conexión** y después **Sincronizar ahora**.

## Cómo funciona

- La app sigue funcionando sin conexión. Al sincronizar manda lo que cambió desde la última vez
  y recibe la planilla completa.
- Si un mismo registro cambió en los dos lados desde la última sincronización, la app te muestra
  las dos versiones y elegís cuál queda. En la sincronización automática no se decide nada solo:
  queda el aviso ⚠ para que lo revises.
- Sincronización automática (se puede apagar): al cerrar la visita, al recuperar la señal y al abrir la app con cambios pendientes.
- Podés corregir datos en la planilla: al editar una fila se actualiza su columna `upd`
  y la app toma el cambio en la próxima sincronización. Si borrás una fila, se borra en la app.
- Las columnas `dias`, `stores`, `promo` e `hist` guardan listas en formato JSON; conviene editarlas desde la app.
- La clave protege el acceso: no la compartas. Cualquiera con la URL **y** la clave puede leer y escribir la planilla.

## Actualizar el script

Cuando cambie `Codigo.gs` (por ejemplo, de la 0.1.3 a la 0.2.1, que agrega las tiendas archivadas): pegá el código nuevo, conservá tu CLAVE,
guardá y en **Implementar → Gestionar implementaciones → editar (lápiz) → Versión: Nueva versión → Implementar**.
La URL /exec no cambia.

## Catálogo de productos (Precios Claros)

El flujo `.github/workflows/catalogo-sepa.yml` arma cada martes un catálogo por código de barras con la base SEPA
de Precios Claros (datos.gob.ar) y lo publica en la rama `catalogo`. La app lo consulta primero al buscar datos
de un código, y después Open Food Facts.

**Importante (nov-2026):** el portal del Gobierno bloquea las descargas desde los servidores de GitHub. El catálogo se arma
desde tu computadora con el programa de la carpeta `local/` (ver `local/LEEME.txt`): descarga y procesa la base, sube un
archivo y el flujo `catalogo-publicar.yml` lo publica.

### Precios de referencia por sucursal (desde la 0.7.0)

- El mismo flujo publica los precios y promos informados por **todas** las sucursales de las zonas de
  `.github/catalogo-zonas.txt` (barrios de CABA y localidades o partidos de PBA). Al guardar un cambio en ese
  archivo, se aplica en la próxima actualización desde tu computadora.
- En la app, **Datos → Tiendas → Vincular con Precios Claros** (hasta 10 tiendas). Qué sucursales elegiste queda
  en tu celular y en tu planilla (columna `sepa` de Tiendas), no en el repo público.
- Son precios de referencia: se ven en Cargar y Comparar y solo pasan a ser tuyos con **Usar este precio** y
  **Guardar precio**. Si tu precio es más nuevo, el de Precios Claros va al historial. Los que tomaste de ahí
  quedan marcados (columna `src` de Precios).
- Las promos con tarjeta o medio de pago que informa la cadena se muestran como dato; tus medios de pago se siguen cargando en Pagos.
- El script 0.7.0 agrega las columnas `sepa` (Tiendas) y `src` (Precios). Con el script anterior la app sigue
  funcionando y conserva esos datos en el celular.
