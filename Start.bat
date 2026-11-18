@echo off
cd /d "%~dp0"
if exist "%~dp0dist\EptalEmoji.exe" (
    start "" "%~dp0dist\EptalEmoji.exe"
    exit /b 0
)
if exist "%~dp0EptalEmoji.exe" (
    start "" "%~dp0EptalEmoji.exe"
    exit /b 0
)
echo EptalEmoji.exe not found. Build it with PyInstaller first.
pause
