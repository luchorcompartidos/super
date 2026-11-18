@echo off
rem Gondola - actualiza el catalogo y los precios de Precios Claros
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 gondola_catalogo.py %*
) else (
  python gondola_catalogo.py %*
)
echo.
pause
