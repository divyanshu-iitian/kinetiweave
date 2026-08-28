param(
    [switch]$CpuOnly,
    [switch]$SkipStudio
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Da3Root = Join-Path $ProjectRoot ".tools\depth-anything-3"
$Da3Commit = "3d835ec1a5802d64a8b8b15f817a1ab54809bfe4"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    py -3.11 -m venv (Join-Path $ProjectRoot ".venv")
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -e "$ProjectRoot[dev]"

if ($CpuOnly) {
    & $Python -m pip install torch torchvision
} else {
    & $Python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
}

& $Python -m pip install `
    addict `
    einops `
    evo `
    huggingface-hub `
    imageio `
    "moviepy==1.0.3" `
    "numpy<2" `
    omegaconf `
    pillow `
    plyfile `
    pycolmap `
    safetensors

if (-not (Test-Path -LiteralPath $Da3Root -PathType Container)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Da3Root) | Out-Null
    git clone --filter=blob:none https://github.com/ByteDance-Seed/depth-anything-3.git $Da3Root
}
git -C $Da3Root fetch origin $Da3Commit --depth 1
git -C $Da3Root checkout --detach $Da3Commit
& $Python -m pip install --no-deps -e $Da3Root

if (-not $SkipStudio) {
    Push-Location (Join-Path $ProjectRoot "apps\studio")
    try {
        npm install
        npm run build
    } finally {
        Pop-Location
    }
}

& $Python -m kinetiweave.cli doctor
Write-Host "KinetiWeave is ready. Start it with: powershell -File scripts/start.ps1"
