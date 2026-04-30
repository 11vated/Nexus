@echo off
REM ============================================================================
REM ULTIMATE AI WORKSTATION - LAUNCHER
REM 100% Free, Unlimited, World-Class Capabilities
REM ============================================================================

title Ultimate AI Workstation
color 0A
cls

echo.
echo ######################################################################
echo #                                                                    #
echo #          ULTIMATE AI WORKSTATION v3.0                               #
echo #          Free. Unlimited. Production-Ready.                          #
echo #                                                                    #
echo ######################################################################
echo.
echo   [1] OPENCODE          - AI Coding Agent (Desktop)
echo   [2] AIDER            - Terminal Coding Agent
echo   [3] GOOSE            - Desktop AI Assistant
echo   [4] CHAT OLLAMA      - Direct model chat
echo.
echo   ======================================================================
echo   PROJECTS
echo   ======================================================================
echo   [N] New Project      - Enterprise templates
echo   [W] Workspace      - Open working directory
echo.
echo   ======================================================================
echo   MODELS (Local - FREE)
echo   ======================================================================
echo   [Q] Qwen 14B         - Code Generation (BEST)
echo   [D] DeepSeek R1     - Reasoning & Planning
echo   [G] Gemma 26B       - Google Large
echo   [C] CodeLlama       - Meta Code
echo.
echo   ======================================================================
echo   TOOLS
echo   ======================================================================
echo   [T] Tests           - Run test suite
echo   [L] Logs           - View application logs
echo   [M] Monitor        - System monitoring
echo.
echo   ======================================================================
echo   [S] Settings       - Configure system
echo   [R] Restart        - Restart services
echo   [Q] Quit
echo.
echo ######################################################################
echo.

set /p choice="Select: "

if "%choice%"=="1" goto OPENCODE
if "%choice%"=="2" goto AIDER
if "%choice%"=="3" goto GOOSE
if "%choice%"=="4" goto CHAT_OLLAMA

if /i "%choice%"=="N" goto NEW_PROJECT
if /i "%choice%"=="W" goto WORKSPACE

if /i "%choice%"=="Q" goto QWEN_14B
if /i "%choice%"=="D" goto DEEPSEEK
if /i "%choice%"=="G" goto GEMMA
if /i "%choice%"=="C" goto CODELLAMA

if /i "%choice%"=="T" goto TESTS
if /i "%choice%"=="L" goto LOGS
if /i "%choice%"=="M" goto MONITOR

if /i "%choice%"=="S" goto SETTINGS
if /i "%choice%"=="R" goto RESTART
if /i "%choice%"=="Q" exit

goto MAIN

:OPENCODE
echo Launching OpenCode Desktop...
start "" "C:\Users\11vat\AppData\Local\OpenCode\OpenCode.exe"
timeout /t 2 >nul
goto MAIN

:AIDER
echo Launching Aider...
cd agent-system
call venv_aider\Scripts\aider.exe --config aider_ultimate.yaml --no-git
goto MAIN

:GOOSE
echo Launching Goose...
start "" "C:\Users\11vat\Desktop\Goose-win32-x64\dist-windows\Goose.exe"
timeout /t 2 >nul
goto MAIN

:CHAT_OLLAMA
echo.
echo Select model for chat:
echo [1] Qwen (Code)
echo [2] DeepSeek (Reasoning)
echo [3] Gemma (General)
echo.
set /p m="Model: "
if "%m%"=="1" set MODEL=qwen2.5-coder:14b
if "%m%"=="2" set MODEL=deepseek-r1:7b
if "%m%"=="3" set MODEL=gemma4:26b
echo Starting chat with %MODEL%...
echo Type your message or 'quit' to exit
ollama run %MODEL%
goto MAIN

:QWN_14B
echo Starting Qwen 14B...
ollama run qwen2.5-coder:14b
goto MAIN

:DEEPSEEK
echo Starting DeepSeek R1...
ollama run deepseek-r1:7b
goto MAIN

:GEMMA
echo Starting Gemma 26B...
ollama run gemma4:26b
goto MAIN

:CODELLAMA
echo Starting CodeLlama...
ollama run codellama:latest
goto MAIN

:NEW_PROJECT
cls
echo.
echo  =======================================================================
echo  PROJECT TEMPLATES
echo  =======================================================================
echo  [1] Enterprise SaaS     - Full-stack multi-tenant
echo  [2] REST API             - Production API service
echo  [3] Frontend           - Next.js application
echo  [4] CLI Tool           - Command-line application
echo.
set /p t="Select template: "
set /p p="Project name: "

if "%t%"=="1" call python init_project.py %p% saas
if "%t%"=="2" call python init_project.py %p% api
if "%t%"=="3" call python init_project.py %p% frontend
if "%t%"=="4" call python init_project.py %p% cli

echo.
echo Project created! Opening...
start "" explorer workspace\%p%
timeout /t 2 >nul
goto MAIN

:WORKSPACE
echo Opening workspace...
start "" explorer workspace
timeout /t 2 >nul
goto MAIN

:TESTS
echo Running tests...
npm test
pause
goto MAIN

:LOGS
echo Viewing logs...
docker-compose logs -f
pause
goto MAIN

:MONITOR
echo.
echo [1] Docker Stats
[2] Application Logs
[3] API Health
[4] Database Queries
set /p m="Select: "
if "%m%"=="1" docker stats
if "%m%"=="2" docker-compose logs -f app
if "%m%"=="3" curl http://localhost:3000/api/health
if "%m%"=="4" docker-compose exec db psql -U user -d app -c "SELECT * FROM pg_stat_statements LIMIT 10"
pause
goto MAIN

:SETTINGS
cls
echo.
echo  =======================================================================
echo  SETTINGS
echo  =======================================================================
echo  [1] OpenCode Config
echo  [2] Aider Config
echo  [3] Goose Config
echo  [4] Ollama Models
echo  [5] Memory System
echo.
set /p s="Select: "
if "%s%"=="1" notepad "C:\Users\11vat\.config\opencode\opencode.json"
if "%s%"=="2" notepad agent-system\aider_ultimate.yaml
if "%s%"=="3" notepad "C:\Users\11vat\AppData\Roaming\Block\goose\config\config.yaml"
if "%s%"=="4" ollama list
if "%s%"=="5" notepad workspace\memory\context.json
pause
goto MAIN

:RESTART
cls
echo.
echo  =======================================================================
echo  RESTART SERVICES
echo  =======================================================================
echo  [1] Restart Ollama
echo  [2] Restart All Docker
echo  [3] Clear Cache
echo.
set /p r="Select: "
if "%r%"=="1" (
    taskkill /F /IM ollama.exe 2>nul
    timeout /t 2 >nul
    start "" ollama
    echo Ollama restarted
)
if "%r%"=="2" docker-compose restart
if "%r%"=="3" ollama prune
pause
goto MAIN

:MAIN
cls
goto MAIN