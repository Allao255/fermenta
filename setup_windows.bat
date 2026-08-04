@echo off
REM ============================================================
REM  Fermenta - setup do zero (Windows), via winget.
REM  Instala: Git, Python, CMake e o compilador C++
REM  (Visual Studio 2022 Build Tools + workload C++).
REM
REM  >>> RODE COMO ADMINISTRADOR <<<
REM  (clique direito neste arquivo > "Executar como administrador")
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === Fermenta: instalando o toolchain de build ===
echo.

where winget >nul 2>&1
if errorlevel 1 (
  echo [ERRO] O "winget" nao foi encontrado.
  echo Instale/atualize o "App Installer" pela Microsoft Store e rode de novo.
  echo Requer Windows 10 1809+ ou Windows 11.
  pause & exit /b 1
)

set "COMMON=-e --accept-source-agreements --accept-package-agreements"

echo [1/4] Git...
winget install --id Git.Git %COMMON%

echo [2/4] Python 3.12...
winget install --id Python.Python.3.12 %COMMON%

echo [3/4] CMake...
winget install --id Kitware.CMake %COMMON%

echo [4/4] Visual Studio 2022 Build Tools + workload C++ (download grande, aguarde)...
winget install --id Microsoft.VisualStudio.2022.BuildTools %COMMON% ^
  --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

echo.
echo ============================================================
echo  PASSO 1 concluido: ferramentas instaladas.
echo.
echo  >>> AGORA: FECHE esta janela e de dois cliques em  abrir_app.bat  <<<
echo.
echo  (o abrir_app.bat instala o resto e abre o Fermenta sozinho.
echo   Se ele reclamar que nao acha o Python, reinicie o PC e tente
echo   de novo - e' o PATH atualizando.)
echo.
echo  Para compilar um VST3 depois: na GUI use "Export ^& Build VST3 (auto)".
echo ============================================================
pause
