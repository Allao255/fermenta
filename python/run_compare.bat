@echo off
cd /d "%~dp0"
echo Garantindo dependencias (numpy + matplotlib)...
python -m pip install -e ".[gui]" >nul 2>&1
echo Abrindo o comparador de pedais...
python -m fermenta.compare
if errorlevel 1 ( echo. & echo Falhou. Confira se o Python esta instalado e no PATH. & pause )
