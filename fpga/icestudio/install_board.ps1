# Adds the FCL board to an installed Icestudio so the project builds from the Icestudio window.
# Run once from an elevated PowerShell (Run as administrator):
#     powershell -ExecutionPolicy Bypass -File fpga\icestudio\install_board.ps1
# It changes three things, and keeps a .bak copy of each file it edits:
#   1. copies fpga\icestudio\FCL into <Icestudio>\resources\boards\FCL
#   2. adds "FCL" to the ECP5 list in <Icestudio>\resources\boards\menu.json
#   3. adds an "FCL" entry (a copy of ulx3s-85f) to apio's boards.json, so apio accepts --board FCL
param(
    [string]$Icestudio = 'C:\Program Files\icestudio',
    [string]$Apio = "$env:USERPROFILE\.icestudio\venv\Lib\site-packages\apio\resources\boards.json"
)
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'FCL'
$boards = Join-Path $Icestudio 'resources\boards'
if (-not (Test-Path $boards)) { throw "Icestudio boards folder not found: $boards" }

# 1. board definition
$dst = Join-Path $boards 'FCL'
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item (Join-Path $src '*') $dst -Force
Write-Host "copied board definition to $dst"

# 2. board menu (edited as text so the rest of the file is left exactly as it was)
$menuPath = Join-Path $boards 'menu.json'
$menu = [IO.File]::ReadAllText($menuPath)
if ($menu -notmatch '"FCL"') {
    Copy-Item $menuPath "$menuPath.bak" -Force
    $new = $menu -replace '("ulx3s-85f")', '$1,"FCL"'
    if ($new -eq $menu) { throw 'ulx3s-85f not found in menu.json' }
    [IO.File]::WriteAllText($menuPath, $new)
    Write-Host 'added FCL to menu.json'
} else { Write-Host 'menu.json already lists FCL' }

# 3. apio board list
if (Test-Path $Apio) {
    $txt = [IO.File]::ReadAllText($Apio)
    if ($txt -notmatch '"FCL"\s*:') {
        Copy-Item $Apio "$Apio.bak" -Force
        $m = [regex]::Match($txt, '"ulx3s-85f"\s*:\s*\{(?:[^{}]|\{[^{}]*\})*\}')
        if (-not $m.Success) { throw 'ulx3s-85f not found in apio boards.json' }
        $entry = $m.Value -replace '^"ulx3s-85f"', '"FCL"'
        $new = $txt.Substring(0, $m.Index + $m.Length) + ",`n  " + $entry + $txt.Substring($m.Index + $m.Length)
        [IO.File]::WriteAllText($Apio, $new)
        Write-Host 'added FCL to apio boards.json'
    } else { Write-Host 'apio boards.json already lists FCL' }
} else { Write-Warning "apio boards.json not found at $Apio - open Icestudio once so it installs its toolchain, then run this again" }
Write-Host 'Done. Restart Icestudio and choose Select > Board > FCL.'
