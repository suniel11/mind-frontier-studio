@echo off
setlocal

if "%~1"=="" (
  echo Usage:
  echo   upload_to_youtube.bat "C:\path\to\project-folder" [private^|unlisted^|public]
  exit /b 1
)

set "PRIVACY=%~2"
if "%PRIVACY%"=="" set "PRIVACY=private"

python youtube_upload.py "%~1" --privacy "%PRIVACY%"
pause
