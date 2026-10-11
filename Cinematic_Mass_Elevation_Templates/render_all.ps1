<#
.SYNOPSIS
  Render Cinematic Mass Elevation templates (preview or final) and write a summary report.

.DESCRIPTION
  Engine "reference" (default): renders with the bundled Python reference renderer
  (06_AUTOMATION/Scripts/render_title.py). Works without DaVinci Resolve.
  Engine "resolve": DaVinci Resolve has no supported command-line renderer, so this
  mode prints the exact in-Resolve procedure (build_resolve_project.py --render).

  For every template the script validates the manifest, checks required files,
  renders, verifies the output with ffprobe (exists, non-empty, expected duration),
  records success/failure, continues after failures, and writes a report to
  06_AUTOMATION/Validation/render_report_<timestamp>.{md,json}.

.EXAMPLE
  .\render_all.ps1                                 # all templates, final 4K ProRes
  .\render_all.ps1 -Mode preview -Templates T01,T40
  .\render_all.ps1 -Mode final -Resolution 1920x1080 -Codec h264
  .\render_all.ps1 -Templates T05 -Set 'MAIN_TITLE=FAILATHON','SUBTITLE=2026'
#>
[CmdletBinding()]
param(
    [ValidateSet('preview', 'final')] [string] $Mode = 'final',
    [string[]] $Templates = @(),
    [string] $Resolution = '',
    [ValidateSet('', 'h264', 'prores', 'png')] [string] $Codec = '',
    [ValidateSet('reference', 'resolve')] [string] $Engine = 'reference',
    [string[]] $Set = @(),
    [string] $Python = '',
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Scripts = Join-Path $Root '06_AUTOMATION/Scripts'
$TplDir = Join-Path $Root '01_TEMPLATES'
$ValDir = Join-Path $Root '06_AUTOMATION/Validation'

function Find-Exe([string[]] $names) {
    foreach ($n in $names) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { return $c.Source }
    }
    return $null
}

Write-Host "Cinematic Mass Elevation Templates - render ($Mode, engine=$Engine)" -ForegroundColor Cyan
Write-Host "Project: $Root"

if ($Engine -eq 'resolve') {
    Write-Host @"
DaVinci Resolve does not provide a supported command-line render interface.
Render through Resolve like this:
  1. Install the titles:  05_RESOLVE_IMPORT\install_titles.ps1
  2. In Resolve: Workspace > Scripts > build_resolve_project  (see
     00_PROJECT_FILES\DaVinci_Resolve_Project\build_resolve_project.py; pass --render
     when running it externally with Resolve Studio) - it queues one render job per
     template into 04_FINAL_RENDERS\Template_NN.
  3. Or manually: Deliver page > pick the timeline > ProRes 422 HQ / UHD > Add to Render Queue.
See 07_DOCUMENTATION\Rendering_Guide.md.
"@
    exit 0
}

# ---------------------------------------------------------------- dependencies
$missing = @()
if (-not $Python) { $Python = Find-Exe @('python3', 'python', 'py') }
if (-not $Python) { $missing += 'Python 3.10+ (python.org)' }
$ffmpeg = Find-Exe @('ffmpeg')
$ffprobe = Find-Exe @('ffprobe')
if (-not $ffmpeg) { $missing += 'ffmpeg (ffmpeg.org; add to PATH)' }
if (-not $ffprobe) { $missing += 'ffprobe (ships with ffmpeg)' }
if ($Python) {
    $null = & $Python -c "import numpy, cv2, PIL" 2>$null
    if ($LASTEXITCODE -ne 0) { $missing += 'Python packages: pip install numpy opencv-python-headless pillow' }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing dependencies:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 2
}

# ---------------------------------------------------------------- settings
if (-not $Resolution) { if ($Mode -eq 'final') { $Resolution = '3840x2160' } else { $Resolution = '1920x1080' } }
if (-not $Codec) { if ($Mode -eq 'final') { $Codec = 'prores' } else { $Codec = 'h264' } }
$ext = @{ h264 = 'mp4'; prores = 'mov'; png = 'png' }[$Codec]

$dirs = Get-ChildItem -Path $TplDir -Directory | Sort-Object Name
if ($Templates.Count -gt 0) {
    $want = @($Templates | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { $_.Trim().ToUpper() })
    $have = @($dirs | ForEach-Object { $_.Name.Split('_')[0] })
    foreach ($w in $want) { if ($have -notcontains $w) { Write-Host "Warning: no template folder for $w" -ForegroundColor Yellow } }
    $dirs = $dirs | Where-Object { $want -contains ($_.Name.Split('_')[0]) }
}
if (-not $dirs) { Write-Host 'No matching templates.' -ForegroundColor Red; exit 2 }

New-Item -ItemType Directory -Force -Path $ValDir | Out-Null
$results = @()
$required = @('id', 'name', 'fusion_macro', 'fusion_composition', 'duration_frames', 'frame_rate')

foreach ($d in $dirs) {
    $id = $d.Name.Split('_')[0]
    $r = [ordered]@{ id = $id; template = $d.Name; status = 'FAILED'; output = ''; seconds = 0; message = '' }
    try {
        $mf = Join-Path $d.FullName 'manifest.json'
        if (-not (Test-Path $mf)) { throw 'manifest.json missing' }
        $m = Get-Content $mf -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($k in $required) { if ($null -eq $m.$k) { throw "manifest field '$k' missing" } }
        foreach ($f in @($m.fusion_macro, $m.fusion_composition)) {
            if (-not (Test-Path (Join-Path $d.FullName $f))) { throw "required file missing: $f" }
        }
        if ($Mode -eq 'preview') {
            $outDir = Join-Path $d.FullName 'preview'
            $out = Join-Path $outDir ("{0}_preview_{1}.{2}" -f $d.Name, $Resolution, $ext)
        } else {
            $outDir = Join-Path $Root ('04_FINAL_RENDERS/Template_' + $id.Substring(1))
            $out = Join-Path $outDir ("{0}_{1}.{2}" -f $d.Name, $Resolution, $ext)
        }
        New-Item -ItemType Directory -Force -Path $outDir | Out-Null
        $argsList = @((Join-Path $Scripts 'render_title.py'), $id, '--res', $Resolution, '--codec', $Codec, '--out', $out)
        foreach ($s in $Set) { $argsList += @('--set', $s) }
        Write-Host ("[{0}] rendering -> {1}" -f $id, $out)
        if ($DryRun) { $r.status = 'DRYRUN'; $r.output = $out; $results += [pscustomobject]$r; continue }
        $sw = [Diagnostics.Stopwatch]::StartNew()
        & $Python @argsList
        $code = $LASTEXITCODE
        $sw.Stop()
        $r.seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        if ($code -ne 0) { throw "renderer exit code $code" }
        if ($Codec -ne 'png') {
            if (-not (Test-Path $out) -or (Get-Item $out).Length -lt 10000) { throw 'output missing or truncated' }
            $dur = & $ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 $out
            $expected = [double]$m.duration_frames / [double]$m.frame_rate
            if ([math]::Abs([double]$dur - $expected) -gt 0.15) { throw "duration $dur s, expected $expected s" }
        }
        $r.status = 'OK'; $r.output = $out
    } catch {
        $r.message = $_.Exception.Message
        Write-Host ("[{0}] FAILED: {1}" -f $id, $r.message) -ForegroundColor Red
    }
    $results += [pscustomobject]$r
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$json = Join-Path $ValDir "render_report_$stamp.json"
$md = Join-Path $ValDir "render_report_$stamp.md"
$results | ConvertTo-Json -Depth 4 | Set-Content -Path $json -Encoding UTF8
$lines = @("# Render report $stamp", '', "Mode: $Mode  Resolution: $Resolution  Codec: $Codec  Engine: $Engine", '',
    '| Template | Status | Seconds | Output / message |', '|---|---|---|---|')
foreach ($r in $results) { $lines += ('| {0} | {1} | {2} | {3}{4} |' -f $r.template, $r.status, $r.seconds, $r.output, $r.message) }
$ok = @($results | Where-Object { $_.status -eq 'OK' }).Count
$lines += ''; $lines += "$ok / $($results.Count) succeeded."
$lines | Set-Content -Path $md -Encoding UTF8
Write-Host ''
Write-Host "$ok / $($results.Count) succeeded. Report: $md" -ForegroundColor Cyan
if ($ok -ne $results.Count -and -not $DryRun) { exit 1 }
