# Open the FCL project for review: KiCad home screen, schematic on the left half, PCB on the right half.
# The schematic and PCB editors are opened FROM the project manager (Ctrl+E / Ctrl+P), so they run inside the
# kicad.exe process and are linked: cross-probing (click a part in one, it highlights in the other) works.
# usage: powershell -ExecutionPolicy Bypass -File scripts\open_kicad.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$bin  = 'C:\Program Files\KiCad\10.0\bin'
$pro  = Join-Path $root 'FCL.kicad_pro'

Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices;
public static class W {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  public static List<KeyValuePair<IntPtr,string>> Windows(uint pid) {
    var res = new List<KeyValuePair<IntPtr,string>>();
    EnumWindows((h, l) => {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) {
        var sb = new StringBuilder(512); GetWindowText(h, sb, 512);
        if (sb.Length > 0) res.Add(new KeyValuePair<IntPtr,string>(h, sb.ToString()));
      }
      return true; }, IntPtr.Zero);
    return res;
  }
  // Ctrl+<key> sent to whatever window is in front
  public static void Ctrl(byte vk) {
    keybd_event(0x11, 0, 0, UIntPtr.Zero); keybd_event(vk, 0, 0, UIntPtr.Zero);
    keybd_event(vk, 0, 2, UIntPtr.Zero);   keybd_event(0x11, 0, 2, UIntPtr.Zero);
  }
}
'@

function Find-Win($proc, $pattern) {
  foreach ($kv in [W]::Windows([uint32]$proc.Id)) { if ($kv.Value -match $pattern) { return $kv.Key } }
  return [IntPtr]::Zero
}
function Wait-Win($proc, $pattern, $sec) {
  for ($i = 0; $i -lt $sec * 4; $i++) {
    $h = Find-Win $proc $pattern
    if ($h -ne [IntPtr]::Zero) { return $h }
    Start-Sleep -Milliseconds 250
  }
  return [IntPtr]::Zero
}
function Focus($h) {
  [void][W]::ShowWindow($h, 9)
  # Windows only lets a background process take the foreground right after a key event: tap Alt first.
  [W]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [W]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
  [void][W]::SetForegroundWindow($h)
  Start-Sleep -Milliseconds 400
}

# Standalone eeschema.exe / pcbnew.exe windows are NOT linked to the project; warn if any are open.
$loose = Get-Process -Name eeschema, pcbnew -ErrorAction SilentlyContinue
if ($loose) { Write-Warning "standalone eeschema/pcbnew running (not linked to the project): close them for cross-probing" }

# Reuse a running KiCad only if it already has FCL open; another project's KiCad is left alone.
$k = Get-Process -Name kicad -ErrorAction SilentlyContinue | Where-Object { (Find-Win $_ 'FCL') -ne [IntPtr]::Zero } | Select-Object -First 1
if (-not $k) { $k = Start-Process -FilePath (Join-Path $bin 'kicad.exe') -ArgumentList "`"$pro`"" -WorkingDirectory $root -PassThru }
$hh = Wait-Win $k '^(?!.*Editor).*KiCad' 60   # project manager, not an editor frame
if ($hh -eq [IntPtr]::Zero) { throw 'KiCad project manager window did not appear' }

$hs = Find-Win $k 'Schematic Editor'
if ($hs -eq [IntPtr]::Zero) { Focus $hh; [W]::Ctrl(0x45); $hs = Wait-Win $k 'Schematic Editor' 90 }   # Ctrl+E
$hp = Find-Win $k 'PCB Editor'
if ($hp -eq [IntPtr]::Zero) { Focus $hh; [W]::Ctrl(0x50); $hp = Wait-Win $k 'PCB Editor' 120 }         # Ctrl+P
if ($hs -eq [IntPtr]::Zero -or $hp -eq [IntPtr]::Zero) { throw "editor window missing (schematic $hs, pcb $hp)" }

$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$half = [int]($wa.Width / 2)
# Two passes: KiCad frames sometimes resize themselves once the document finishes loading.
foreach ($pass in 1..2) {
  foreach ($h in $hs, $hp) { [void][W]::ShowWindow($h, 9) }   # restore (un-maximize)
  [void][W]::MoveWindow($hs, $wa.X,         $wa.Y, $half,              $wa.Height, $true)
  [void][W]::MoveWindow($hp, $wa.X + $half, $wa.Y, $wa.Width - $half,  $wa.Height, $true)
  Start-Sleep -Seconds 3
}
Focus $hh   # home screen in front; schematic and PCB tiled behind it
"home $hh  schematic $hs (left)  pcb $hp (right)  all in kicad.exe pid $($k.Id) (linked)"
