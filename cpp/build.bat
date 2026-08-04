@echo off
REM Build the fermenta VST3 + Standalone. Run from a "x64 Native Tools Command
REM Prompt for VS 2022" (has cmake + compiler on PATH), or just double-click if
REM cmake and git are on your PATH. First run downloads JUCE (needs internet).
setlocal
cd /d "%~dp0"
echo === Configuring (downloads JUCE the first time) ===
cmake -B build -G "Visual Studio 17 2022" -A x64
if errorlevel 1 goto :err
echo === Building Release ===
cmake --build build --config Release
if errorlevel 1 goto :err
echo.
echo === DONE ===
echo Standalone: build\WdfViolaMXR_artefacts\Release\Standalone\fermenta MXR.exe
echo VST3:       build\WdfViolaMXR_artefacts\Release\VST3\fermenta MXR.vst3
goto :eof
:err
echo.
echo Build failed. Check that CMake and Git are installed and on PATH,
echo and that you have an internet connection for the first (JUCE) download.
