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

Cuando cambie `Codigo.gs` (por ejemplo, de la versión 0.1.2 a la 0.1.3): pegá el código nuevo, conservá tu CLAVE,
guardá y en **Implementar → Gestionar implementaciones → editar (lápiz) → Versión: Nueva versión → Implementar**.
La URL /exec no cambia.
