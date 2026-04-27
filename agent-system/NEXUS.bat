@echo off
REM ============================================================================
REM NEXUS ULTIMATE LAUNCHER - AUTONOMOUS + ALL MODELS
REM ============================================================================
REM Full autonomy: Self-healing, auto-discovery, daemon mode
REM 
REM Usage:
REM   NEXUS [option]
REM   NEXUS auto "task description"
REM   NEXUS daemon
REM
REM Options:
REM   [1] qwen2.5-coder:14b      - Best code generation (9GB)
REM   [2] qwen2.5-coder:7b       - Fast code (4.7GB)
REM   [3] deepseek-r1:7b          - Debugging/Reasoning (4.7GB)
REM   [4] gpt-5-nano             - GPT-5 Nano (2.5GB)
REM   [5] minimax-max-m2.5-free  - MiniMax (8GB)
REM
REM   [V] llava                 - Vision analysis
REM   [A] OpenCode             - AI-native IDE
REM   [G] Goose               - Autonomous CLI
REM   [N] Dashboard           - Web dashboard
REM
REM   [E] Evolution           - Genetic algorithm mode
REM   [D] Daemon              - Background task runner
REM   [S] Status              - System status check
REM   [X] Auto                - Autonomous execution
REM ============================================================================

echo.
echo +============================================================+
echo ^|     NEXUS ULTIMATE - AUTONOMOUS + ALL MODELS             ^|
echo +============================================================+
echo ^|
echo ^|  Code Generation:                                        ^|
echo ^|    [1] qwen2.5-coder:14b   - Best (9GB)                 ^|
echo ^|    [2] qwen2.5-coder:7b    - Fast (4.7GB)               ^|
echo ^|    [3] gpt-5-nano          - GPT-5 Nano                 ^|
echo ^|    [4] minimax-max-m2.5-free - MiniMax                  ^|
echo ^|
echo ^|  Reasoning:                                               ^|
echo ^|    [5] deepseek-r1:7b    - Debugging (4.7GB)           ^|
echo ^|
echo ^|  Vision:                                                  ^|
echo ^|    [V] llava              - Screen analysis             ^|
echo ^|
echo ^|  Tools:                                                   ^|
echo ^|    [A] OpenCode         - AI-native IDE                 ^|
echo ^|    [G] Goose           - Autonomous CLI                 ^|
echo ^|    [N] Dashboard       - Web interface                 ^|
echo ^|
echo ^|  Advanced:                                                ^|
echo ^|    [E] Evolution       - Genetic algorithm             ^|
echo ^|    [D] Daemon          - Background task runner        ^|
echo ^|    [S] Status         - System status check           ^|
echo ^|    [X] Auto           - Autonomous execution         ^|
echo ^|    [P] Autopilot      - Full autonomy (Recommended) ^|
echo ^|
echo +============================================================+
echo.

set /p choice="Select option: "

REM ============================================================================
REM CODE MODELS
REM ============================================================================

if "%choice%"=="1" goto code_14b
if "%choice%"=="2" goto code_7b
if "%choice%"=="3" goto gpt5_nano
if "%choice%"=="4" goto minimax

REM ============================================================================
REM REASONING
REM ============================================================================

if "%choice%"=="5" goto deepseek

REM ============================================================================
REM VISION
REM ============================================================================

if /i "%choice%"=="V" goto vision

REM ============================================================================
REM TOOLS
REM ============================================================================

if /i "%choice%"=="A" goto opencode
if /i "%choice%"=="G" goto goose
if /i "%choice%"=="N" goto nexus

REM ============================================================================
REM ADVANCED
REM ============================================================================

if /i "%choice%"=="E" goto evolution
if /i "%choice%"=="D" goto daemon
if /i "%choice%"=="S" goto status
if /i "%choice%"=="X" goto autonomous
if /i "%choice%"=="P" goto autopilot

goto help

REM ============================================================================
REM MODEL LAUNCHERS
REM ============================================================================

:code_14b
echo [1] Starting qwen2.5-coder:14b...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
call venv_aider\Scripts\activate
aider --model qwen2.5-coder:14b
goto end

:code_7b
echo [2] Starting qwen2.5-coder:7b...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
call venv_aider\Scripts\activate
aider --model qwen2.5-coder:7b
goto end

:gpt5_nano
echo [3] Starting GPT-5 Nano...
ollama run gpt-5-nano
goto end

:minimax
echo [4] Starting MiniMax...
ollama run minimax-max-m2.5-free
goto end

:deepseek
echo [5] Starting DeepSeek R1...
ollama run deepseek-r1:7b
goto end

:vision
echo [V] Starting Vision (llava)...
echo Describe or analyze your image when prompted.
ollama run llava
goto end

REM ============================================================================
REM TOOL LAUNCHERS
REM ============================================================================

:opencode
echo [A] Starting OpenCode...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent
start "" "C:\Users\11vat\AppData\Local\OpenCode\OpenCode.exe"
goto end

:goose
echo [G] Starting Goose...
start "" "C:\Users\11vat\Desktop\Goose-win32-x64\dist-windows\Goose.exe"
goto end

:nexus
echo [N] Starting NEXUS Dashboard...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system\nexus_dashboard
python server.py
goto end

REM ============================================================================
REM ADVANCED MODES
REM ============================================================================

:evolution
echo [E] Starting Evolutionary Mode...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
call venv_aider\Scripts\activate
python nexus_orchestrator.py --evolve --pop-size 10 --max-gens 20
goto end

:daemon
echo [D] Starting Autonomous Daemon...
echo Will watch .nexus/tasks/ for new tasks...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
python nexus_autonomous.py --daemon
goto end

:status
echo [S] Checking System Status...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
python nexus_autonomous.py --status
pause
goto end

:autonomous
echo [X] Starting Autonomous Executor...
echo Enter your task when prompted:
echo (Type 'quit' to exit)
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
python nexus_autonomous.py
goto end

:autopilot
echo [P] Starting FULL AUTOPILOT...
echo.
echo   Features: Scheduler, File Watcher, Health Monitor,
echo             Git Automation, Rollback, Error Tracking
echo.
python nexus_autopilot.py --daemon
goto end

:daemon
echo [D] Starting Autonomous Daemon...
echo Will watch .nexus/tasks/ for new tasks...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
python nexus_autonomous.py --daemon
goto end

:status
echo [S] Checking System Status...
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
python nexus_autonomous.py --status
pause
goto end

:autonomous
echo [X] Starting Autonomous Executor...
echo Enter your task when prompted:
echo (Type 'quit' to exit)
cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
python nexus_autonomous.py
goto end

:help
echo.
echo Valid choices: 1-5, V, A, G, N, E, D, S, X
echo.
echo Quick commands:
echo   NEXUS auto "build a REST API"     - Execute task
echo   NEXUS daemon                      - Background mode
echo   NEXUS status                      - Check tools
timeout /t 3

:end
echo.
echo +============================================================+
echo ^|  Done!                                                  ^|
echo +============================================================+

REM ============================================================================
REM AUTO MODE (for command line usage)
REM ============================================================================

if /i "%1"=="auto" (
    cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
    python nexus_autonomous.py %2
    goto end
)

if /i "%1"=="daemon" (
    cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
    python nexus_autonomous.py --daemon
    goto end
)

if /i "%1"=="status" (
    cd C:\Users\11vat\Desktop\Copilot\Aider-Local-llm-agent\agent-system
    python nexus_autonomous.py --status
    goto end
)