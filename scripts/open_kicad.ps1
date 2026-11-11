# Open the FCL project for review: KiCad home screen, schematic on the left half, PCB on the right half.
# usage: powershell -ExecutionPolicy Bypass -File scripts\open_kicad.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$bin  = 'C:\Program Files\KiCad\10.0\bin'

Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class W {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
'@

function Start-Or-Get($name, $exe, $file) {
  $p = Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $p) { $p = Start-Process -FilePath (Join-Path $bin $exe) -ArgumentList "`"$file`"" -WorkingDirectory $root -PassThru }
  return $p
}
function Wait-Window($p, $sec) {
  for ($i = 0; $i -lt $sec * 4; $i++) {
    $p.Refresh()
    if ($p.MainWindowHandle -ne 0) { return $p.MainWindowHandle }
    Start-Sleep -Milliseconds 250
  }
  throw "no window for $($p.ProcessName)"
}

$home_ = Start-Or-Get 'kicad'    'kicad.exe'    (Join-Path $root 'FCL.kicad_pro')
$sch   = Start-Or-Get 'eeschema' 'eeschema.exe' (Join-Path $root 'FCL.kicad_sch')
$pcb   = Start-Or-Get 'pcbnew'   'pcbnew.exe'   (Join-Path $root 'FCL.kicad_pcb')
$hh = Wait-Window $home_ 60; $hs = Wait-Window $sch 90; $hp = Wait-Window $pcb 120

$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$half = [int]($wa.Width / 2)
# Two passes: KiCad frames sometimes resize themselves once the document finishes loading.
foreach ($pass in 1..2) {
  foreach ($h in $hs, $hp) { [void][W]::ShowWindow($h, 9) }   # restore (un-maximize)
  [void][W]::MoveWindow($hs, $wa.X,         $wa.Y, $half,              $wa.Height, $true)
  [void][W]::MoveWindow($hp, $wa.X + $half, $wa.Y, $wa.Width - $half,  $wa.Height, $true)
  Start-Sleep -Seconds 3
}
[void][W]::ShowWindow($hh, 9)         # the home screen can start minimized: restore it
[void][W]::SetForegroundWindow($hh)   # home screen in front; schematic and PCB tiled behind it
"home $hh  schematic $hs (left)  pcb $hp (right)"
