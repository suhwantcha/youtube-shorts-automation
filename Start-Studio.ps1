param([int]$Port = 8080)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '먼저 setup.ps1을 실행해주세요.' }
Write-Host "Tech Shorts Studio: http://127.0.0.1:$Port"
Write-Host '이 창을 열어두세요. 종료하려면 Ctrl+C를 누르세요.'
& $pythonPath -m tech_shorts serve --port $Port
