# Levanta el servidor. Toda la configuracion sale de .env, no de este archivo.
# El router hace: 201.252.170.251:9000 (afuera) -> esta maquina:PUERTO.
# Si cambias .env: Ctrl+C y volver a correr (--reload recarga el codigo, no las variables).

$python = "$PSScriptRoot\.venv\Scripts\python.exe"

# Lo que la app va a usar de verdad, leido del .env:
$cfg = & $python -c "from app import config; print(config.BASE_URL); print(config.PUERTO)"
$baseUrl = $cfg[0]
$puerto  = $cfg[1]

Write-Host ""
Write-Host "BASE_URL (.env):  $baseUrl"
Write-Host "Escuchando en:    0.0.0.0:$puerto"
Write-Host ""
Write-Host "Invitacion:  $baseUrl/"
Write-Host "Panel:       $baseUrl/admin"
Write-Host "Escaner:     $baseUrl/admin/escaner"
Write-Host ""
Write-Host "Los QR codifican $baseUrl/i/{codigo}"
Write-Host ""

& $python -m uvicorn app.main:app --host 0.0.0.0 --port $puerto --reload
