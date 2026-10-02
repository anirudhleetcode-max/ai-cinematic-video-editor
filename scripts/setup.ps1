# Windows setup (PowerShell). Usage:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
function Need($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
Write-Host "== Checking toolchain"
if (-not (Need "python")) { throw "Python 3.10+ is required (https://www.python.org/downloads/ - tick 'Add to PATH')" }
if (-not (Need "node")) { throw "Node.js 20+ is required (https://nodejs.org)" }
if (-not (Need "ffmpeg") -or -not (Need "ffprobe")) {
  Write-Host "FFmpeg not found. Install with:  winget install Gyan.FFmpeg   (then reopen the terminal)"
  Write-Host "or set FFMPEG_BIN / FFPROBE_BIN in .env to full paths of ffmpeg.exe / ffprobe.exe"
  exit 1
}
$filters = (ffmpeg -hide_banner -filters 2>$null) -join "`n"
if ($filters -notmatch " ass ") { Write-Warning "ffmpeg built without libass - titles/captions will not render (use a 'full' build)" }
Write-Host "== Python environment (.venv)"
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\python.exe -m pip install -e "services/engine[dev]"
Write-Host "== Web app"
Push-Location apps\web; npm install; Pop-Location
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "== Health check (GPU encoders are verified by a test encode)"
& .\.venv\Scripts\python.exe -c "import sys,json; sys.path.insert(0,'services/engine'); from editor.hw import diagnostics; d=diagnostics(); print(json.dumps({k:d[k] for k in ('ffmpeg','encoders','selected_encoder','gpu','cpu_count','ram_total_gb')}, indent=1))"
Write-Host "`nDone. Start everything with:  npm run dev"
