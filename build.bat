@echo off
echo ========================================
echo YouTube Downloader Build Script
echo ========================================
echo.

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first
    pause
    exit /b 1
)

echo Building...
echo.

python build.py

if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete!
echo ========================================
echo.
echo Executable: dist\YouTubeDownloader.exe
echo Portable:   dist\YouTubeDownloader_Portable\
echo.
pause
