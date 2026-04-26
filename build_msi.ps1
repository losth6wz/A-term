$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    throw "Python venv not found at $py"
}

Write-Host "[1/4] Installing/updating Python build tools..."
& $py -m pip install --upgrade pip pyinstaller | Out-Host

Write-Host "[2/4] Building A-term executable (one-folder)..."
& $py -m PyInstaller --noconfirm --windowed --name A-term --add-data "aterm.conf;." main.py | Out-Host

Write-Host "[3/4] Installing/updating WiX CLI (dotnet tool)..."
$dotnetTools = Join-Path $env:USERPROFILE '.dotnet\tools'
if (-not ($env:Path -split ';' | Where-Object { $_ -eq $dotnetTools })) {
    $env:Path = "$dotnetTools;$env:Path"
}

& dotnet tool update --global wix --version 4.* | Out-Host

Write-Host "[4/4] Building MSI..."
New-Item -ItemType Directory -Force -Path (Join-Path $root 'dist-installer') | Out-Null

$wxsPath = Join-Path $root 'installer\A-term.wxs'
$appSourceDir = Join-Path $root 'dist\A-term'
$msiOut = Join-Path $root 'dist-installer\A-term-Setup.msi'

& wix build `
  $wxsPath `
  -ext WixToolset.UI.wixext `
  -d "AppSourceDir=$appSourceDir" `
  -o $msiOut | Out-Host

Write-Host "Done. MSI output: dist-installer\A-term-Setup.msi"
