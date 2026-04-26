# A-term build script — produces dist\A-term.exe + dist-installer\A-term-Setup.msi
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root      = $PSScriptRoot
$distDir   = Join-Path $root "dist"
$outDir    = Join-Path $root "dist-installer"
$exeSource = Join-Path $distDir "A-term.exe"
$confSource= Join-Path $root "aterm.conf"
$wxsPath   = Join-Path $root "installer\A-term.wxs"
$msiOut    = Join-Path $outDir "A-term-Setup.msi"
$assetsDir = Join-Path $root "assets"
$iconIco   = Join-Path $assetsDir "icon.ico"
$iconPng   = Join-Path $assetsDir "icon.png"

# ── Step 1: Python build tools ───────────────────────────────────────────────
Write-Host "[1/4] Installing/updating Python build tools..."
& "$root\.venv\Scripts\python.exe" -m pip install --upgrade pip pyinstaller pillow | Out-Null

if (-not (Test-Path $iconIco) -and (Test-Path $iconPng)) {
    Write-Host "[1/4] Converting assets/icon.png to assets/icon.ico..."
    & "$root\.venv\Scripts\python.exe" -c "from PIL import Image; img=Image.open(r'$iconPng'); img.save(r'$iconIco', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
}

# ── Step 2: PyInstaller one-file exe ─────────────────────────────────────────
Write-Host "[2/4] Building A-term executable (one-file)..."
Push-Location $root
$pyiArgs = @("--onefile", "--windowed", "--name", "A-term")
if (Test-Path $iconIco) {
    $pyiArgs += @("--icon", $iconIco)
}
$pyiArgs += "main.py"
& "$root\.venv\Scripts\pyinstaller.exe" @pyiArgs
Pop-Location

if (-not (Test-Path $exeSource)) {
    Write-Error "PyInstaller did not produce $exeSource"
}

# ── Step 3: WiX CLI ──────────────────────────────────────────────────────────
Write-Host "[3/4] Installing/updating WiX CLI (dotnet tool)..."
dotnet tool update --global wix --version "4.*" 2>&1 | Out-Null
$env:PATH = "$env:USERPROFILE\.dotnet\tools;$env:PATH"

# ── Step 4: Build MSI ────────────────────────────────────────────────────────
Write-Host "[4/4] Building MSI..."
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
& wix build $wxsPath `
    -d "ExeSource=$exeSource" `
    -d "ConfSource=$confSource" `
    -o $msiOut

if (-not (Test-Path $msiOut)) {
    Write-Error "WiX did not produce $msiOut"
}

Write-Host "Done. MSI output: dist-installer\A-term-Setup.msi"
