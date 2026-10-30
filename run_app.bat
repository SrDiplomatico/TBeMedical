@echo off
setlocal
REM Run from source on a developer machine. Works from any folder location.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)

echo Starting PDF Form Data Extractor...
".venv\Scripts\python.exe" src\main.py
endlocal
exit /b 0

:fail
echo Setup failed. Make sure Python 3.11+ is installed and on PATH.
pause
endlocal
exit /b 1
