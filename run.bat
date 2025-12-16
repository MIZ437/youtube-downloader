@echo off

REM Activate virtual environment and run without console
if exist "venv\Scripts\pythonw.exe" (
    call venv\Scripts\activate.bat
    start "" pythonw main.py
) else (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first
    pause
)
