@echo off
setlocal
set "ONE_MEMORY_DATA_DIR=%LOCALAPPDATA%\MemHub-Windows\Data"
rem Enable the Kuzu graph store so the SDK runs in "ultra" mode:
rem System 2 cognitive processing, graph projection and episode summaries.
set "ONE_MEMORY_GRAPH_STORE=kuzu"
set "ELECTRON_RUN_AS_NODE="
set "ONE_MEMORY_WEB_URL="
pushd "%~dp0memhub\apps\desktop" || exit /b 1
if not exist "node_modules\electron\dist\electron.exe" goto missing
if not exist "dist\main.js" goto missing
if not exist "..\web\dist\index.html" goto missing
if not exist "..\core\.venv\Scripts\one-memory.exe" goto missing
rem A desktop app outlives the console that started it. Keep its standard
rem handles valid after that console closes; diagnostics are written to disk.
start "" "node_modules\electron\dist\electron.exe" . <nul >nul 2>&1
popd
exit /b 0
:missing
echo MemHub desktop build is missing. See the Windows build script.
pause
exit /b 1
