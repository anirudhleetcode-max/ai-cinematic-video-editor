@echo off
REM FAILATHON AV - one-click spot edit for Windows.
REM Usage:  RUN_FAILATHON.bat  "<media folder>"  "<BGM file>"
REM With no arguments it uses the E-Cell download folder and 01_AUDIO\BGM_FAILATHON.mp3.
setlocal
set "MEDIA=%~1"
if "%MEDIA%"=="" set "MEDIA=C:\Users\aniru\Downloads\Ecellfailthon-20261006T194834Z-1-001\Ecellfailthon"
set "BGM=%~2"
if "%BGM%"=="" set "BGM=%~dp0..\01_AUDIO\BGM_FAILATHON.mp3"

if not exist "%MEDIA%" ( echo Media folder not found: %MEDIA% & pause & exit /b 1 )
if not exist "%BGM%" ( echo BGM not found: %BGM%  - copy the BGM there or pass it as the 2nd argument & pause & exit /b 1 )

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo FFmpeg not found - installing with winget...
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
  echo Close this window and run RUN_FAILATHON.bat again so PATH picks up ffmpeg.
  pause & exit /b 1
)
where python >nul 2>nul
if errorlevel 1 ( echo Python not found - install Python 3.10+ from python.org ^(tick "Add to PATH"^) & pause & exit /b 1 )

python -m pip install --quiet --disable-pip-version-check numpy pillow librosa
python "%~dp0failathon_autoedit.py" --media "%MEDIA%" --bgm "%BGM%" %3 %4 %5 %6 %7 %8 %9
if errorlevel 1 ( echo EDIT FAILED - see messages above & pause & exit /b 1 )

echo.
echo ===== MP4 done: %~dp0..\07_EXPORTS\FAILATHON_AV_FINAL.mp4 =====
echo Now building the DaVinci Resolve project (Resolve must be OPEN)...
python "%~dp0FAILATHON_AV_RESOLVE_SCRIPT.py"
if errorlevel 1 echo Resolve step failed - open Resolve, set Preferences ^> System ^> General ^> External scripting = Local, then run:  python "%~dp0FAILATHON_AV_RESOLVE_SCRIPT.py"
pause
