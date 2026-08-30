param(
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Local environment not found. Run: powershell -File scripts/setup-da3.ps1"
}

$Studio = Join-Path $ProjectRoot "apps\studio"
if (-not (Test-Path -LiteralPath (Join-Path $Studio "dist\index.html") -PathType Leaf)) {
    Push-Location $Studio
    try {
        npm install
        npm run build
    } finally {
        Pop-Location
    }
}

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:$Port"
}

Push-Location $ProjectRoot
try {
    & $Python -m kinetiweave.cli serve --port $Port
} finally {
    Pop-Location
}
