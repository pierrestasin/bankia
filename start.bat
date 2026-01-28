@echo off
echo ============================================
echo   BankIA - Demarrage de l'application
echo ============================================
echo.

echo Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou pas dans le PATH
    pause
    exit /b 1
)

echo.
echo Demarrage de l'application Flask...
echo.
echo L'application sera accessible sur: http://localhost:5000
echo.
echo Appuyez sur Ctrl+C pour arreter l'application
echo.

python app.py

pause

