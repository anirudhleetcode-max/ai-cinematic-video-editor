<#
.SYNOPSIS
  Install the Fusion title macros (and optionally the bundled OFL fonts) for DaVinci Resolve.

.DESCRIPTION
  Copies 05_RESOLVE_IMPORT/Fusion_Macros/*.setting into Resolve's per-user Fusion
  templates folder under Templates/Edit/Titles/Cinematic Mass Elevation/, so the
  titles appear in the Edit page > Effects > Titles (Fusion Titles) after a restart.
  Existing files are never overwritten unless -Force is given.

  Default target folders (per user):
    Windows: %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates\Edit\Titles
    macOS:   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/Titles
    Linux:   ~/.local/share/DaVinciResolve/Fusion/Templates/Edit/Titles
  If Resolve shows nothing after a restart, open Effects > Titles, right-click >
  "Show Folder" (or Fusion page > Effects > Templates) to see the folder your version
  uses and pass it with -Target.

.EXAMPLE
  .\install_titles.ps1 -InstallFonts
  .\install_titles.ps1 -Target "D:\ResolveTemplates\Edit\Titles" -Force
#>
[CmdletBinding()]
param(
    [string] $Target = '',
    [switch] $InstallFonts,
    [switch] $Force,
    [switch] $WhatIf
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$src = Join-Path $here 'Fusion_Macros'
$fontsSrc = Join-Path (Split-Path $here -Parent) '02_SHARED_ASSETS/Fonts'
$onWindows = ($env:OS -eq 'Windows_NT')
$onMac = (-not $onWindows) -and (Test-Path '/System/Library')

if (-not $Target) {
    if ($onWindows) { $Target = Join-Path $env:APPDATA 'Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates\Edit\Titles' }
    elseif ($onMac) { $Target = Join-Path $HOME 'Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/Titles' }
    else { $Target = Join-Path $HOME '.local/share/DaVinciResolve/Fusion/Templates/Edit/Titles' }
}
$dest = Join-Path $Target 'Cinematic Mass Elevation'
Write-Host "Installing titles to: $dest"
if (-not $WhatIf) { New-Item -ItemType Directory -Force -Path $dest | Out-Null }
$n = 0; $skipped = 0
foreach ($f in Get-ChildItem -Path $src -Filter '*.setting' | Sort-Object Name) {
    $to = Join-Path $dest $f.Name
    if ((Test-Path $to) -and -not $Force) { Write-Host "  exists, skipped (use -Force): $($f.Name)" -ForegroundColor Yellow; $skipped++; continue }
    if (-not $WhatIf) { Copy-Item $f.FullName $to -Force }
    $n++
}
Write-Host "$n title macro(s) installed, $skipped skipped."

if ($InstallFonts) {
    $fonts = Get-ChildItem -Path $fontsSrc -Recurse -Include '*.ttf', '*.otf'
    if ($onWindows) {
        $fdir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
        New-Item -ItemType Directory -Force -Path $fdir | Out-Null
        $reg = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
        foreach ($ft in $fonts) {
            $to = Join-Path $fdir $ft.Name
            if (-not $WhatIf) {
                if (-not (Test-Path $to)) { Copy-Item $ft.FullName $to }
                New-ItemProperty -Path $reg -Name ($ft.BaseName + ' (TrueType)') -Value $to -PropertyType String -Force | Out-Null
            }
        }
    } else {
        if ($onMac) { $fdir = Join-Path $HOME 'Library/Fonts' } else { $fdir = Join-Path $HOME '.local/share/fonts' }
        New-Item -ItemType Directory -Force -Path $fdir | Out-Null
        foreach ($ft in $fonts) { $to = Join-Path $fdir $ft.Name; if (-not $WhatIf -and -not (Test-Path $to)) { Copy-Item $ft.FullName $to } }
        if (-not $onMac -and (Get-Command fc-cache -ErrorAction SilentlyContinue) -and -not $WhatIf) { fc-cache -f $fdir | Out-Null }
    }
    Write-Host "$($fonts.Count) font file(s) installed for the current user (OFL licensed; licences in 02_SHARED_ASSETS/Fonts)."
}
Write-Host 'Restart DaVinci Resolve, then look in Edit page > Effects > Toolbox/Titles > Fusion Titles.' -ForegroundColor Cyan
