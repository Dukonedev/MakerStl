@echo off
REM ============================================================
REM  MakerStl — Windows build script
REM  Run from repo root after installing all deps:
REM    pip install -r requirements.txt pyinstaller
REM ============================================================

echo [1/3] Building .exe with PyInstaller ...
pyinstaller MakerStl.spec --noconfirm
if errorlevel 1 (
    echo BUILD FAILED
    exit /b 1
)

echo [2/3] Creating Installer directory ...
if exist builds\MakerStl-win rd /s /q builds\MakerStl-win
mkdir builds\MakerStl-win
xcopy /E /I /Y dist\MakerStl builds\MakerStl-win\MakerStl

echo [3/3] Done!
echo.
echo   Output: builds\MakerStl-win\MakerStl\MakerStl.exe
echo.
echo   To distribute as a single folder zip:
echo     powershell Compress-Archive -Path builds\MakerStl-win\MakerStl -DestinationPath builds\MakerStl-win.zip
echo.
echo   Or use Inno Setup / NSIS to create a proper installer.
