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

# ── Step 1: Python build tools ───────────────────────────────────────────────
Write-Host "[1/4] Installing/updating Python build tools..."
& "$root\.venv\Scripts\python.exe" -m pip install --upgrade pip pyinstaller | Out-Null

# ── Step 2: PyInstaller one-file exe ─────────────────────────────────────────
Write-Host "[2/4] Building A-term executable (one-file)..."
Push-Location $root
& "$root\.venv\Scripts\pyinstaller.exe" `
    --onefile --windowed --name A-term main.py
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
