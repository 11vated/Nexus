@echo off
chcp 65001 >nul
mode con: cols=100 lines=35
color 0a

:start
cls
echo.
echo  █████╗ ██╗      ██████╗  ██████╗ ██████╗ ██╗████████╗██╗  ██╗███╗   ███╗
echo. ██╔══██╗██║     ██╔════╝ ██╔═══██╗██╔══██╗██║╚══██╔══╝██║  ██║████╗ ████║
echo. ███████║██║     ██║  ███╗██║   ██║██████╔╝██║   ██║   ███████║██║ ██║██║
echo. ██╔══██║██║     ██║   ██║██║   ██║██╔══██╗██║   ██║   ██╔══██║██║██║██║
echo. ██║  ██║███████╗╚██████╔╝╚██████╔╝██║  ██║██║   ██║   ██║  ██║██╔██╗██║
echo. ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝
echo.
echo                    ULTIMATE LOCAL AI WORKSTATION
echo              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo  [1] OpenCode Desktop          [A] OpenCode with Model Select
echo  [2] Aider (Terminal)          [B] Aider with DeepSeek-R1
echo  [3] Goose Desktop             [C] Goose with Custom Config
echo.
echo  ═════════════════════════════════════════════════════════════
echo.
echo  [P] Profound System            [M] Run MCP Servers
echo  [L] Ollama Models              [N] Ollama Chat (direct)
echo.
echo  ═════════════════════════════════════════════════════════════
echo.
echo  [S] System Status              [D] Docker Dashboard
echo  [R] Research Mode (web)        [W] WebUI Chat
echo.
echo  ═════════════════════════════════════════════════════════════
echo.
echo  [Q] Quit
echo.
echo.
set /p choice="Select option: "

if /i "%choice%"=="1" start "" "C:\Users\11vat\AppData\Local\OpenCode\OpenCode.exe"
if /i "%choice%"=="2" cd /d "C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent" && call venv_aider\Scripts\activate && aider
if /i "%choice%"=="3" start "" "C:\Users\11vat\Desktop\Goose-win32-x64\dist-windows\Goose.exe"
if /i "%choice%"=="a" start "" "C:\Users\11vat\AppData\Local\OpenCode\OpenCode.exe" --model qwen2.5-coder:14b
if /i "%choice%"=="b" cd /d "C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent" && call venv_aider\Scripts\activate && aider --model deepseek-r1:7b
if /i "%choice%"=="c" start "" "C:\Users\11vat\AppData\Roaming\Block\goose\config\config.yaml"
if /i "%choice%"=="p" cd /d "C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent" && python agent-system/profound_system.py
if /i "%choice%"=="m" cd /d "C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system\mcp-servers" && npm run start
if /i "%choice%"=="l" ollama list
if /i "%choice%"=="n" ollama run qwen2.5-coder:14b
if /i "%choice%"=="s" echo. & echo System Status: & echo - RAM: & wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value & echo - Ollama: & ollama list & pause
if /i "%choice%"=="d" docker-compose -f "C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\docker-compose.yml" ps 2>nul || echo Docker not running
if /i "%choice%"=="r" start "" "http://localhost:11434"
if /i "%choice%"=="w" start "" "http://localhost:8080"
if /i "%choice%"=="q" exit

echo.
pause
goto start