@echo off
setlocal

cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found in PATH.
    pause
    exit /b 1
)

python -c "import yaml, tqdm" 2>nul || (
    echo [*] Installing launcher requirements ^(PyYAML, tqdm^)...
    python -m pip install --quiet -r tools\startme\requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install tools\startme\requirements.txt.
        pause
        exit /b 1
    )
)

python tools\startme\startme.py %*
