@echo off
REM ============================================================
REM  Build the fermenta GUI into a standalone Windows app (.exe)
REM  Output: python\dist\fermenta.exe   (double-click to run)
REM ============================================================
cd /d "%~dp0"

echo [1/3] Instalando dependencias de build (pyinstaller, numpy, matplotlib)...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install pyinstaller numpy "matplotlib>=3.5" >nul 2>&1
if errorlevel 1 (
  echo.
  echo Falha ao instalar dependencias. Verifique se o Python esta no PATH.
  pause & exit /b 1
)

echo [2/3] Limpando builds anteriores...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

echo [3/3] Empacotando com PyInstaller (pode levar 1-3 min)...
python -m PyInstaller --noconfirm fermenta_gui.spec
if errorlevel 1 (
  echo.
  echo Build falhou. Rode "python -m fermenta.gui" para ver o erro em detalhe.
  pause & exit /b 1
)

echo.
echo ============================================================
echo  Pronto!  O aplicativo esta em:  python\dist\fermenta.exe
echo  E so dar dois cliques nele. Nao precisa de Python instalado.
echo ============================================================
pause
