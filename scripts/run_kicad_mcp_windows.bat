@echo off
REM scripts/run_kicad_mcp_windows.bat - Standalone Windows runner for KiCad MCP
setlocal

REM Resolve project root relative to script location
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"

set "KICAD_MCP_PROJECT_DIR=%PROJECT_ROOT%\hardware"
set "KICAD_MCP_PROFILE=agent_full"
set "KICAD_MCP_OPERATING_MODE=experimental"

REM Prepend standard KiCad and uv locations to PATH
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;C:\Program Files\KiCad\10.0\bin;C:\Program Files\KiCad\9.0\bin;C:\Program Files\KiCad\8.0\bin;%PATH%"

REM Enable 8.3 short temp path for named pipe IPC socket matching KiCad GUI
for %%I in ("%LOCALAPPDATA%\Temp") do set "KICAD_API_SOCKET=ipc://%%~sI\kicad\api.sock"

uvx kicad-mcp-pro
