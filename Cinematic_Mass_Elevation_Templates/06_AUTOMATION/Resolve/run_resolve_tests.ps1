<#
.SYNOPSIS
  Audit this Windows machine for DaVinci Resolve testing, then run the CMET Resolve test harness.

.DESCRIPTION
  -AuditOnly  : read-only. Reports OS, disk, Resolve install/version, running state, scripting
                modules, Python, fonts, installed titles. Writes
                06_AUTOMATION/Validation/resolve/baseline_audit_<time>.{json,md} (user name redacted).
  (default)   : audit, then
                1. installs the 40 title macros + OFL fonts with install_titles.ps1 (never overwrites;
                   stops if an older, different copy of a title is already installed),
                2. installs an in-Resolve launcher script into Fusion\Scripts\Utility (never overwrites),
                3. sets RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB / PYTHONPATH for this process only,
                4. runs resolve_harness.py against the running Resolve (dedicated new test project
                   CMET_ResolveTest_<runid>; existing projects are not touched),
                5. runs analyze_resolve_run.py on the results.
  -Analyze <runid> : only re-run the analyzer on an existing run.

  Nothing here changes system settings, security policy or Resolve preferences. If Resolve
  requires a manual step (start Resolve, enable external scripting, set generator duration),
  the script says exactly what to do and stops.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\run_resolve_tests.ps1 -AuditOnly
  powershell -ExecutionPolicy Bypass -File .\run_resolve_tests.ps1 -Templates T01
  powershell -ExecutionPolicy Bypass -File .\run_resolve_tests.ps1            # all 40
#>
[CmdletBinding()]
param(
    [switch] $AuditOnly,
    [string[]] $Templates = @(),
    [switch] $NoRender,
    [string] $RunId = '',
    [string] $Analyze = '',
    [string] $Python = '',
    [switch] $AllowExistingTitles
)
$ErrorActionPreference = 'Stop'
$Here = $PSScriptRoot
$Root = (Resolve-Path (Join-Path $Here '..\..')).Path
$ValDir = Join-Path $Root '06_AUTOMATION\Validation\resolve'
New-Item -ItemType Directory -Force -Path $ValDir | Out-Null
$onWindows = ($env:OS -eq 'Windows_NT')
$PF = if ($env:ProgramFiles) { $env:ProgramFiles } else { 'C:\Program Files' }
$PD = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } else { 'C:\ProgramData' }
$AD = if ($env:APPDATA) { $env:APPDATA } else { "$HOME\AppData\Roaming" }

function Redact([string]$s) {
    if (-not $s) { return $s }
    if ($env:USERPROFILE) { $s = $s.Replace($env:USERPROFILE, '%USERPROFILE%') }
    if ($env:USERNAME) { $s = $s.Replace($env:USERNAME, '<user>') }
    if ($HOME -and $HOME.Length -gt 3) { $s = $s.Replace($HOME, '~') }
    return $s
}
function Find-Python {
    if ($Python) { return $Python }
    foreach ($n in @('py', 'python', 'python3')) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { return $c.Source }
    }
    return $null
}

# ------------------------------------------------------------------ audit
$a = [ordered]@{ time = (Get-Date).ToString('s'); windows = $onWindows }
if ($onWindows) {
    $os = Get-CimInstance Win32_OperatingSystem
    $a.os = "$($os.Caption) $($os.Version) ($($os.OSArchitecture))"
} else { $a.os = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription }
$drive = (Get-Item $Root).PSDrive
$a.project_drive_free_gb = [math]::Round($drive.Free / 1GB, 1)
$a.project_root = Redact $Root
$exeCandidates = @("$PF\Blackmagic Design\DaVinci Resolve\Resolve.exe")
$exe = $exeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
$a.resolve_installed = [bool]$exe
if ($exe) {
    $vi = (Get-Item $exe).VersionInfo
    $a.resolve_exe = $exe
    $a.resolve_file_version = $vi.FileVersion
    $a.resolve_product_version = $vi.ProductVersion
    $a.resolve_product_name = $vi.ProductName
    $a.fusionscript_dll = Test-Path ("$(Split-Path $exe)\fusionscript.dll")
}
$proc = Get-Process -Name 'Resolve' -ErrorAction SilentlyContinue
$a.resolve_running = [bool]$proc
$api = "$PD\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
$a.scripting_api_dir = Test-Path $api
$a.scripting_module = Test-Path ("$api\Modules\DaVinciResolveScript.py")
$py = Find-Python
$a.python = $py
if ($py) {
    $a.python_version = (& $py -c "import sys,struct;print(sys.version.split()[0], str(struct.calcsize('P')*8)+'-bit')" 2>$null)
    $null = & $py -c "import numpy, cv2" 2>$null
    $a.python_numpy_cv2 = ($LASTEXITCODE -eq 0)
}
$a.ffmpeg = [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)
$fams = @('Anton', 'Bebas Neue', 'Black Ops One', 'Russo One', 'Cinzel', 'Cinzel Decorative', 'Marcellus SC', 'Orbitron',
          'Audiowide', 'Staatliches', 'Teko', 'Ramabhadra', 'Noto Sans Telugu')
$fontNames = @()
foreach ($k in @('HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts', 'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')) {
    if (Test-Path $k) { $fontNames += (Get-ItemProperty $k).PSObject.Properties.Name }
}
$a.fonts_missing = @($fams | Where-Object { $f = $_; -not ($fontNames | Where-Object { $_ -like "$f*" }) })
$titlesDir = "$AD\Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates\Edit\Titles\Cinematic Mass Elevation"
$a.titles_installed = if (Test-Path $titlesDir) { (Get-ChildItem $titlesDir -Filter *.setting).Count } else { 0 }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$a | ConvertTo-Json | ForEach-Object { Redact $_ } | Set-Content (Join-Path $ValDir "baseline_audit_$stamp.json") -Encoding UTF8
$md = @("# Resolve test baseline audit ($stamp)", '', '| Item | Value |', '|---|---|')
foreach ($k in $a.Keys) { $md += ('| {0} | {1} |' -f $k, (Redact ([string]($a[$k] -join ', ')))) }
$md | Set-Content (Join-Path $ValDir "baseline_audit_$stamp.md") -Encoding UTF8
Write-Host ($md -join "`n")
Write-Host "Audit written to 06_AUTOMATION\Validation\resolve\baseline_audit_$stamp.md" -ForegroundColor Cyan

$blockers = @()
if (-not $onWindows) { $blockers += 'Not running on Windows (this launcher targets the Windows Resolve install).' }
if (-not $a.resolve_installed) { $blockers += 'DaVinci Resolve not found at the default install path.' }
if (-not $a.scripting_module) { $blockers += 'Resolve scripting module (Developer\Scripting\Modules\DaVinciResolveScript.py) not found.' }
if (-not $py) { $blockers += 'Python 3 (64-bit) not found on PATH.' }
if ($a.project_drive_free_gb -lt 5) { $blockers += 'Less than 5 GB free on the project drive.' }
if ($AuditOnly) {
    if ($blockers) { Write-Host "Blockers:`n - $($blockers -join "`n - ")" -ForegroundColor Yellow }
    exit 0
}

# ------------------------------------------------------------------ analyze only
$harness = Join-Path $Here 'resolve_harness.py'
$analyzer = Join-Path $Here 'analyze_resolve_run.py'
if ($Analyze) {
    & $py $analyzer --run $Analyze
    exit $LASTEXITCODE
}
if ($blockers) { Write-Host "Cannot run Resolve tests:`n - $($blockers -join "`n - ")" -ForegroundColor Red; exit 2 }

# ------------------------------------------------------------------ install titles + fonts (no overwrite)
$src = Join-Path $Root '05_RESOLVE_IMPORT\Fusion_Macros'
if ((Test-Path $titlesDir) -and -not $AllowExistingTitles) {
    $stale = @()
    foreach ($f in Get-ChildItem $src -Filter *.setting) {
        $dst = "$titlesDir\$($f.Name)"
        if ((Test-Path $dst) -and ((Get-FileHash $dst).Hash -ne (Get-FileHash $f.FullName).Hash)) { $stale += $f.Name }
    }
    if ($stale) {
        Write-Host "These installed titles differ from this repository (older version?):`n - $($stale -join "`n - ")" -ForegroundColor Red
        Write-Host 'Testing them would not test this collection. Move that folder aside yourself (it is not deleted automatically), or re-run with -AllowExistingTitles to test the installed copies.' -ForegroundColor Red
        exit 3
    }
}
& (Join-Path $Root '05_RESOLVE_IMPORT\install_titles.ps1') -InstallFonts

# ------------------------------------------------------------------ in-Resolve launcher stub (no overwrite)
$ids = @($Templates | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { $_.Trim().ToUpper() })
$stubDir = "$AD\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
New-Item -ItemType Directory -Force -Path $stubDir | Out-Null
$stubDst = "$stubDir\CMET_Run_Resolve_Tests.py"
$stub = (Get-Content (Join-Path $Here 'CMET_Run_Resolve_Tests_stub.py') -Raw).Replace('__CMET_ROOT__', $Root).Replace('__TEMPLATES__', ($ids -join ','))
if ((Test-Path $stubDst) -and ((Get-Content $stubDst -Raw) -ne $stub)) {
    Write-Host "Not overwriting existing $stubDst (different content)." -ForegroundColor Yellow
} else { Set-Content -Path $stubDst -Value $stub -Encoding UTF8 }

# ------------------------------------------------------------------ connect + run
if (-not $a.resolve_running) {
    Write-Host @'
ACTION NEEDED: start DaVinci Resolve (open any project or the Project Manager), then run this script again.
Before the first run also set: Preferences > User > Editing > Standard Generator Duration = 10 seconds
(so inserted titles are long enough for every template).
'@ -ForegroundColor Yellow
    exit 4
}
$env:RESOLVE_SCRIPT_API = $api
$env:RESOLVE_SCRIPT_LIB = "$(Split-Path $exe)\fusionscript.dll"
$env:PYTHONPATH = "$env:PYTHONPATH;$("$api\Modules")"
if (-not $RunId) { $RunId = $stamp }
$args2 = @($harness, '--root', $Root, '--run-id', $RunId)
if ($ids) { $args2 += @('--templates', ($ids -join ',')) }
if ($NoRender) { $args2 += '--no-render' }
& $py @args2
$code = $LASTEXITCODE
if ($code -eq 2) {
    Write-Host @"
ACTION NEEDED: Resolve is running but refused the external scripting connection.
 * DaVinci Resolve Studio: Preferences > System > General > 'External scripting using' = Local, restart Resolve, run again.
 * Free edition (external scripting not available): inside Resolve choose
   Workspace > Scripts > Utility > CMET_Run_Resolve_Tests   (installed just now), wait for it to finish, then run
   .\run_resolve_tests.ps1 -Analyze <run id printed in Resolve's console>
"@ -ForegroundColor Yellow
    exit 2
}
if ($code -ne 0) { Write-Host "Harness exited with $code - see 06_AUTOMATION\Validation\resolve_runs\$RunId\harness_log.txt" -ForegroundColor Red; exit $code }
if (-not $a.python_numpy_cv2) { Write-Host 'Install analyzer deps: pip install numpy opencv-python, then: .\run_resolve_tests.ps1 -Analyze ' $RunId -ForegroundColor Yellow; exit 0 }
& $py $analyzer --run $RunId
Write-Host "Results: 06_AUTOMATION\Validation\resolve_runs\$RunId\resolve_test_results.md (merged into 06_AUTOMATION\Validation\resolve_test_results.json)" -ForegroundColor Cyan
