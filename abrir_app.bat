@echo off
REM ============================================================
REM  Fermenta - instala as dependencias do Python e ABRE o app.
REM  Rode DEPOIS do setup_windows.bat (com o terminal reaberto,
REM  ou simplesmente de dois cliques neste arquivo).
REM ============================================================
setlocal
cd /d "%~dp0\python"

REM --- procura o Python (python ou py) ---
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY ( where py >nul 2>&1 && set "PY=py" )

if not defined PY (
  echo.
  echo [ERRO] Python nao foi encontrado.
  echo.
  echo 1^) Rode o "setup_windows.bat" como ADMINISTRADOR ^(instala o Python^).
  echo 2^) FECHE e REABRA esta janela ^(ou reinicie o PC^).
  echo 3^) De dois cliques neste arquivo de novo.
  echo.
  pause & exit /b 1
)

echo Usando: %PY%
echo Instalando dependencias (numpy + matplotlib)... pode demorar na 1a vez.
%PY% -m pip install --upgrade pip >nul 2>&1
%PY% -m pip install -e ".[gui]"
if errorlevel 1 (
  echo.
  echo [ERRO] Falha ao instalar as dependencias. Verifique sua internet.
  pause & exit /b 1
)

echo.
echo Abrindo o Fermenta...
%PY% -m fermenta.gui
if errorlevel 1 (
  echo.
  echo O app fechou com erro. Rode "%PY% -m fermenta.gui" no terminal para ver o detalhe.
  pause
)
