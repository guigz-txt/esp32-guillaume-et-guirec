@echo off
cd /d "%~dp0"
echo ========================================
echo              COGIP - Serveur
echo ========================================
echo.
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERREUR : installation des dependances impossible.
    pause
    exit /b 1
)
echo.
py run_server.py
pause
