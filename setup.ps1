$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $basePython = (Get-Command python -ErrorAction Stop).Source
    & $basePython -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 이상이 필요합니다.' }
}
& $pythonPath -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw '패키지 설치에 실패했습니다.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
& $pythonPath -m tech_shorts doctor
if ($LASTEXITCODE -ne 0) { throw '실행 환경 점검에 실패했습니다.' }
Write-Host '설치 완료. .env에 키를 입력한 뒤 Start-Studio.ps1을 실행하세요.'
