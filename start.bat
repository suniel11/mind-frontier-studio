@echo off
title Mind Frontier Studio
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed.
  echo Install Python 3.11 or newer, then run this file again.
  pause
  exit /b 1
)

if not exist .env (
  copy .env.example .env >nul
  echo.
  echo Add your OpenAI API key to the .env file.
  notepad .env
  echo.
  echo Save the file, then run start.bat again.
  pause
  exit /b 0
)

if not exist .venv (
  echo Creating virtual environment...
  py -m venv .venv
)

call .venv\Scripts\activate
echo Installing packages...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Starting Mind Frontier Studio...
start "" http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
