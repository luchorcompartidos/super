# Gondola - tarea semanal para actualizar el catalogo de Precios Claros
# Miercoles 03:00. Si la computadora estaba apagada, corre apenas este disponible,
# pero solo cuando lleva 10 minutos sin uso (espera hasta 12 horas) y con prioridad baja.
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $dir 'gondola_catalogo.py'
$exe = (Get-Command pyw.exe -ErrorAction SilentlyContinue).Source
$argu = "-3 `"$script`" --auto"
if (-not $exe) { $exe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source; $argu = "`"$script`" --auto" }
if (-not $exe) { Write-Host 'No se encontro Python. Instalalo desde python.org (tilda "Add python.exe to PATH") y volve a probar.'; exit 1 }
if (-not (Test-Path (Join-Path $dir 'config.txt'))) { Write-Host 'Primero corre una vez "Actualizar catalogo.bat" para cargar el token.'; exit 1 }
$action = New-ScheduledTaskAction -Execute $exe -Argument $argu -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At 3am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -RunOnlyIfIdle `
  -IdleDuration (New-TimeSpan -Minutes 10) -IdleWaitTimeout (New-TimeSpan -Hours 12) -DontStopOnIdleEnd `
  -ExecutionTimeLimit (New-TimeSpan -Hours 3) -Priority 7 -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'Gondola - Actualizar catalogo' -Action $action -Trigger $trigger -Settings $settings `
  -Description 'Descarga la base SEPA de Precios Claros, arma los precios de referencia y los publica para la app Gondola.' -Force | Out-Null
Write-Host 'Listo: tarea "Gondola - Actualizar catalogo" creada (miercoles 03:00, solo con la computadora sin uso).'
Write-Host 'Se puede ver, ejecutar o borrar desde el Programador de tareas de Windows.'
