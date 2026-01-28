@echo off
echo ============================================
echo   Installation de BankIA
echo ============================================
echo.

echo Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou pas dans le PATH
    echo.
    echo Veuillez installer Python depuis https://www.python.org/downloads/
    echo IMPORTANT: Cochez "Add Python to PATH" pendant l'installation
    echo.
    pause
    exit /b 1
)

echo Python trouve!
echo.

echo Installation des dependances...
python -m pip install --upgrade pip
python -m pip install Flask requests python-dateutil pandas

if errorlevel 1 (
    echo.
    echo ERREUR lors de l'installation des dependances
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation terminee avec succes!
echo ============================================
echo.
echo N'oubliez pas de configurer config.py avec vos parametres Dolibarr
echo.
echo Pour lancer l'application: python app.py
echo.
pause

