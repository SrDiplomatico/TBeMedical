@echo off
setlocal
REM ============================================================
REM  Build a portable Windows package of PDF Form Data Extractor
REM  Output: dist\PDFFormExtractor\  and  dist\PDFFormExtractor.zip
REM  Requires: Python 3.11+ on PATH (python.org installer)
REM ============================================================
cd /d "%~dp0"

if not exist ".venv-build\Scripts\python.exe" (
    echo [1/5] Creating build virtual environment...
    python -m venv .venv-build || goto :fail
)

echo [2/5] Installing dependencies...
".venv-build\Scripts\python.exe" -m pip install --upgrade pip --quiet || goto :fail
".venv-build\Scripts\python.exe" -m pip install -r requirements-dev.txt --quiet || goto :fail

echo [3/5] Running PyInstaller...
if exist "dist\PDFFormExtractor" rmdir /s /q "dist\PDFFormExtractor"
".venv-build\Scripts\python.exe" -m PyInstaller PDFFormExtractor.spec --noconfirm --clean || goto :fail

echo [4/5] Self-test of the built executable...
"dist\PDFFormExtractor\PDFFormExtractor.exe" --self-test > "dist\selftest.log" 2>&1
set SELFTEST=%ERRORLEVEL%
type "dist\selftest.log"
if not "%SELFTEST%"=="0" (
    echo Self-test FAILED. See dist\selftest.log
    goto :fail
)

echo [5/5] Zipping...
if exist "dist\PDFFormExtractor.zip" del "dist\PDFFormExtractor.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PDFFormExtractor' -DestinationPath 'dist\PDFFormExtractor.zip' -Force" || goto :fail

echo.
echo BUILD SUCCEEDED
echo   Folder: %~dp0dist\PDFFormExtractor\
echo   Zip:    %~dp0dist\PDFFormExtractor.zip
echo Copy the zip to another Windows PC, unzip anywhere, run PDFFormExtractor.exe.
echo Google Chrome must be installed on that PC.
endlocal
exit /b 0

:fail
echo.
echo BUILD FAILED (see messages above)
endlocal
exit /b 1
