@echo off
cd /d "%~dp0"

REM Check if Python is already installed
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python is already installed.
    echo Running main.py...
    python main.py
    if %errorlevel% neq 0 (
        echo The script encountered an error.
        pause
    )
    exit
)

REM Define the URL for the Python installer
set "pythonInstaller=https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe"
set "installerName=python-3.13.0-amd64.exe"

REM Downloading Python installer using PowerShell
echo Downloading Python 3.13.0...
powershell -Command "Invoke-WebRequest -Uri '%pythonInstaller%' -OutFile '%installerName%'"

REM Running the installer interactively
echo Installing Python 3.13.0...
start "" "%installerName%"

REM Clean up
echo Cleaning up...
del "%installerName%"

echo Installation started.

REM Wait for user to finish installation before proceeding
pause

REM Check if Python is installed successfully after installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python installation failed.
    pause
    exit /b
)

REM Run the Python script
echo Running main.py...
python main.py

if %errorlevel% neq 0 (
    echo The script encountered an error.
    pause
)

exit