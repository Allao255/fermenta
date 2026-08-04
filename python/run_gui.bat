@echo off
REM Abre a GUI do fermenta. Deixe este arquivo na pasta  fermenta\python.
cd /d "%~dp0"
echo Garantindo dependencias (numpy + matplotlib)...
python -m pip install -e ".[gui]" >nul 2>&1
echo Abrindo a interface...
python -m fermenta.gui
if errorlevel 1 (
  echo.
  echo Falhou. Confira se o Python esta instalado e no PATH.
  pause
)
