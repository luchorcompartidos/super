@echo off
rem Gondola - crea (o reemplaza) la tarea semanal en el Programador de tareas de Windows
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0programar.ps1"
echo.
pause
