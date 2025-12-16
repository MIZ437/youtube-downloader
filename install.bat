@echo off
echo ========================================
echo YouTube Downloader Installer
echo ========================================
echo.

REM Check Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed
    echo Please install from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python OK
echo.

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing packages...
echo (This may take a few minutes)
echo.

pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Failed to install packages
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo Run 'run.bat' to start the application
echo.
pause
