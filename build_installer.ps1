$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    throw "Python venv not found at $py"
}

Write-Host "[1/3] Installing build tools..."
& $py -m pip install --upgrade pyinstaller | Out-Host

Write-Host "[2/3] Building A-term executable..."
& $py -m PyInstaller --noconfirm --windowed --name A-term main.py | Out-Host

Write-Host "[3/3] Building installer with Inno Setup..."
$innoCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$iscc = $innoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup not found. Install Inno Setup 6, then run this script again."
}

& $iscc (Join-Path $root 'installer\A-term.iss') | Out-Host

Write-Host "Done. Installer output is in dist-installer\"
