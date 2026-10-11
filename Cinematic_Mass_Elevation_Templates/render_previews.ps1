<#
.SYNOPSIS
  Regenerate the 1080p previews, thumbnails, manifests, contact sheet and HTML catalog.

.DESCRIPTION
  Runs the build pipeline in 06_AUTOMATION/Scripts:
    build.py sources   - regenerate Fusion .setting/.comp + docs
    build.py previews  - render 1080p previews (parallel) + thumbnails
    build.py validate  - Lua parse, structural checks, ffprobe checks -> manifest.json
    catalog.py         - contact sheet, TEMPLATE_CATALOG.html/.md
  Continues past individual template failures (they are reported by validate).

.EXAMPLE
  .\render_previews.ps1                 # everything, 4 parallel jobs
  .\render_previews.ps1 -Templates T01,T07 -Jobs 2
#>
[CmdletBinding()]
param(
    [string[]] $Templates = @(),
    [int] $Jobs = 4,
    [string] $Python = '',
    [switch] $SkipSources
)
$ErrorActionPreference = 'Stop'
$Scripts = Join-Path $PSScriptRoot '06_AUTOMATION/Scripts'
if (-not $Python) {
    foreach ($n in @('python3', 'python', 'py')) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { $Python = $c.Source; break }
    }
}
if (-not $Python) { Write-Host 'Python 3 not found (install from python.org).' -ForegroundColor Red; exit 2 }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Host 'ffmpeg not found on PATH.' -ForegroundColor Red; exit 2 }
$null = & $Python -c "import numpy, cv2, PIL, lupa" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Missing Python packages. Run: pip install numpy opencv-python-headless pillow lupa' -ForegroundColor Red
    exit 2
}
$ids = @($Templates | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { $_.Trim().ToUpper() })
Push-Location $Scripts
try {
    if (-not $SkipSources) { & $Python build.py sources @ids }
    & $Python build.py previews @ids --jobs $Jobs
    & $Python build.py validate @ids
    & $Python catalog.py
} finally { Pop-Location }
Write-Host 'Done. Open TEMPLATE_CATALOG.html to browse.' -ForegroundColor Cyan
