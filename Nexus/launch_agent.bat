@echo off
REM Universal Agent Launcher
REM Installs MCPs on demand and launches agent

setlocal enabledelayedexpansion

set AGENT=%1
set TASK=%2

if "%AGENT%"=="" (
    echo Usage: agent.bat [aider^|goose^|claude] "task"
    exit /b 1
)

REM Install essential MCPs if not installed
echo Checking MCP servers...
npx -y @modelcontextprotocol/server-filesystem --help >nul 2>&1 || npx -y @modelcontextprotocol/server-filesystem
npx -y @modelcontextprotocol/server-git --help >nul 2>&1 || npx -y @modelcontextprotocol/server-git
npx -y @modelcontextprotocol/server-playwright --help >nul 2>&1 || npx -y @modelcontextprotocol/server-playwright
npx -y @modelcontextprotocol/server-memory --help >nul 2>&1 || npx -y @modelcontextprotocol/server-memory

echo Launching %AGENT%...

if /i "%AGENT%"=="aider" (
    cd agent-system
    call venv_aider\Scripts\aider.exe --config aider_config.yaml --no-git --message "%TASK%"
) else if /i "%AGENT%"=="goose" (
    start "" "%USERPROFILE%\Desktop\Goose-win32-x64\dist-windows\Goose.exe"
) else if /i "%AGENT%"=="claude" (
    claude --add --dangerously-skip-permissions "%TASK%"
) else (
    echo Unknown agent: %AGENT%
    exit /b 1
)

echo Done!