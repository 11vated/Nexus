@echo off
chcp 65001 >nul
mode con: cols=120 lines=40
color 02

:start
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════════════════╗
echo  ║                                                                              ║
echo  ║     █████╗ ██╗      ██████╗  ██████╗ ██████╗ ██╗████████╗██╗  ██╗ ██████╗   ║
echo  ║    ██╔══██╗██║     ██╔════╝ ██╔═══██╗██╔══██╗██║╚══██╔══╝██║  ██║██╔═══██╗  ║
echo  ║    ███████║██║     ██║  ███╗██║   ██║██████╔╝██║   ██║   ███████║██║   ██║  ║
echo  ║    ██╔══██║██║     ██║   ██║██║   ██║██╔══██╗██║   ██║   ██╔══██║██║   ██║  ║
echo  ║    ██║  ██║███████╗╚██████╔╝╚██████╔╝██║  ██║██║   ██║   ██║  ██║╚██████╔╝  ║
echo  ║    ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝   ║
echo  ║                                                                              ║
echo  ║                    ULTIMATE LOCAL AI WORKSTATION                            ║
echo  ║                         Command Center v3.0                                  ║
echo  ╚══════════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔══════════════════════════════════════════════════════════════════════════════╗
echo  ║  🚀 LAUNCH INTERFACES                                                         ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║                                                                              ║
echo  ║  [1] NEXUS Dashboard      - Ultimate AI Command Center (WebUI)      ★ NEW   ║
echo  ║  [2] OpenCode Desktop     - AI-native IDE with MCP support                   ║
echo  ║  [3] Aider                - Terminal-first pair programmer                   ║
echo  ║  [4] Goose Desktop        - Autonomous CLI agent                             ║
echo  ║  [5] Profound System      - Multi-agent orchestrator (Python)                ║
echo  ║  [6] Unified CLI          - All tools in one terminal                        ║
echo  ║                                                                              ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║  🧠 MODELS                                                                   ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║                                                                              ║
echo  ║  [C] Code Models         - qwen2.5-coder:14b, codellama                      ║
echo  ║  [R] Reasoning Models    - deepseek-r1:7b                                    ║
echo  ║  [U] Uncensored          - dolphin-mistral                                   ║
echo  ║  [F] Fast Models         - qwen2.5-coder:7b, deepseek-r1:1.5b                ║
echo  ║                                                                              ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║  🔧 UTILITIES                                                                 ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║                                                                              ║
echo  ║  [L] List Models         - Show all available Ollama models                  ║
echo  ║  [O] Ollama Chat         - Direct chat with selected model                   ║
echo  ║  [S] System Status       - Check Ollama, RAM, disk usage                    ║
echo  ║  [M] Model Info          - Show model details and capabilities              ║
echo  ║  [P] Project Analyzer    - Analyze codebase structure                       ║
echo  ║  [W] WebGPU Test         - Test WebGPU capabilities                          ║
echo  ║                                                                              ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║  ⚡ QUICK ACTIONS                                                             ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║                                                                              ║
echo  ║  [G] Generate Code       - Describe what to build                           ║
echo  ║  [A] Analyze Project    - Deep codebase analysis                            ║
echo  ║  [D] Debug Problem      - AI debugging assistant                            ║
echo  ║  [B] Brainstorm         - Architecture discussion                           ║
echo  ║                                                                              ║
echo  ╠══════════════════════════════════════════════════════════════════════════════╣
echo  ║                                                                              ║
echo  ║  [Q] Quit                                                                         ║
echo  ╚══════════════════════════════════════════════════════════════════════════════╝
echo.
echo  Current: %current_model% 
echo.

set /p choice="Select option: "

if /i "%choice%"=="1" (
    echo.
    echo  Starting NEXUS Dashboard...
    echo  Opening http://localhost:5555
    echo.
    cd /d "%~dp0agent-system\nexus_dashboard"
    start python server.py
    timeout /t 3 /nobreak >nul
    start http://localhost:5555
    goto start
)

if /i "%choice%"=="2" (
    echo.
    echo  Launching OpenCode Desktop...
    start "" "C:\Users\11vat\AppData\Local\OpenCode\OpenCode.exe"
    goto start
)

if /i "%choice%"=="3" (
    echo.
    echo  Launching Aider...
    cd /d "%~dp0"
    call venv_aider\Scripts\activate
    aider --model qwen2.5-coder:14b
    goto start
)

if /i "%choice%"=="4" (
    echo.
    echo  Launching Goose Desktop...
    start "" "C:\Users\11vat\Desktop\Goose-win32-x64\dist-windows\Goose.exe"
    goto start
)

if /i "%choice%"=="5" (
    echo.
    echo  Starting Profound System...
    cd /d "%~dp0agent-system"
    python profound_system.py
    goto start
)

if /i "%choice%"=="6" (
    echo.
    echo  Starting Unified CLI...
    cd /d "%~dp0agent-system"
    python unified_cli.py
    goto start
)

if /i "%choice%"=="c" (
    echo.
    echo  Available Code Models:
    echo  =====================
    echo  [1] qwen2.5-coder:14b  - Best overall code (9GB)
    echo  [2] qwen2.5-coder:7b   - Fast code (4.7GB)
    echo  [3] codellama          - Meta code (3.8GB)
    echo  [4] gemma4:26b         - Large general (17GB)
    echo.
    set /p model_choice="Select model: "
    if "%model_choice%"=="1" set current_model=qwen2.5-coder:14b
    if "%model_choice%"=="2" set current_model=qwen2.5-coder:7b
    if "%model_choice%"=="3" set current_model=codellama
    if "%model_choice%"=="4" set current_model=gemma4:26b
    echo  Model set to: %current_model%
    timeout /t 2 >nul
    goto start
)

if /i "%choice%"=="r" (
    echo.
    echo  Available Reasoning Models:
    echo  ============================
    echo  [1] deepseek-r1:7b      - Best reasoning (4.7GB)
    echo  [2] deepseek-r1:1.5b    - Fast reasoning (1.1GB)
    echo.
    set /p model_choice="Select model: "
    if "%model_choice%"=="1" set current_model=deepseek-r1:7b
    if "%model_choice%"=="2" set current_model=deepseek-r1:1.5b
    echo  Model set to: %current_model%
    timeout /t 2 >nul
    goto start
)

if /i "%choice%"=="u" (
    echo.
    echo  Uncensored Models:
    echo  =================
    echo  [1] dolphin-mistral    - Uncensored coding (4.1GB)
    echo  [2] dolphin-mixtral    - Best uncensored (26GB)
    echo.
    set /p model_choice="Select model: "
    if "%model_choice%"=="1" set current_model=dolphin-mistral
    if "%model_choice%"=="2" set current_model=dolphin-mixtral:8x7b
    echo  Model set to: %current_model%
    timeout /t 2 >nul
    goto start
)

if /i "%choice%"=="f" (
    echo.
    echo  Fast Models:
    echo  ============
    echo  [1] qwen2.5-coder:7b         - Fast code (4.7GB)
    echo  [2] deepseek-r1:1.5b         - Fast reasoning (1.1GB)
    echo  [3] qwen2.5-coder:1.5b       - Tiny code (1.6GB)
    echo.
    set /p model_choice="Select model: "
    if "%model_choice%"=="1" set current_model=qwen2.5-coder:7b
    if "%model_choice%"=="2" set current_model=deepseek-r1:1.5b
    if "%model_choice%"=="3" set current_model=qwen2.5-coder:1.5b-base-q8_0
    echo  Model set to: %current_model%
    timeout /t 2 >nul
    goto start
)

if /i "%choice%"=="l" (
    echo.
    echo  ═══════════════════════════════
    echo  ║ AVAILABLE OLLAMA MODELS ║
    echo  ═══════════════════════════════
    ollama list
    echo.
    pause
    goto start
)

if /i "%choice%"=="o" (
    echo.
    set /p ollama_model="Model (default qwen2.5-coder:14b): "
    if "%ollama_model%"=="" set ollama_model=qwen2.5-coder:14b
    ollama run %ollama_model%
    goto start
)

if /i "%choice%"=="s" (
    echo.
    echo  ═══════════════════════════════
    echo  ║ SYSTEM STATUS ║
    echo  ═══════════════════════════════
    echo.
    echo  [OLLAMA]
    ollama list
    echo.
    echo  [SYSTEM MEMORY]
    wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value
    echo.
    echo  [DISK]
    wmic logicaldisk get size,freespace,caption
    echo.
    pause
    goto start
)

if /i "%choice%"=="m" (
    echo.
    echo  ═══════════════════════════════
    echo  ║ MODEL INFORMATION ║
    echo  ═══════════════════════════════
    echo.
    echo  Code Generation:
    echo    - qwen2.5-coder:14b  - Best overall, 9GB RAM
    echo    - qwen2.5-coder:7b   - Fast, 4.7GB RAM  
    echo    - codellama          - Meta, 3.8GB RAM
    echo.
    echo  Reasoning:
    echo    - deepseek-r1:7b     - Best reasoning, 4.7GB RAM
    echo    - deepseek-r1:1.5b   - Fast reasoning, 1.1GB RAM
    echo.
    echo  Uncensored:
    echo    - dolphin-mistral    - Uncensored coding, 4.1GB RAM
    echo.
    pause
    goto start
)

if /i "%choice%"=="p" (
    echo.
    set /p proj_path="Project path (or Enter for current): "
    if "%proj_path%"=="" set proj_path=.
    echo.
    echo  Analyzing project...
    python "%~dp0agent-system\unified_cli.py" 2>nul || (
        echo  Analyzing: %proj_path%
        echo  Files: 
        dir /s /b "%proj_path%\*.py" 2>nul | find /c /v ""
        dir /s /b "%proj_path%\*.js" 2>nul | find /c /v ""
        dir /s /b "%proj_path%\*.ts" 2>nul | find /c /v ""
    )
    pause
    goto start
)

if /i "%choice%"=="w" (
    echo.
    echo  Testing WebGPU...
    echo  Opening test page...
    start "" "http://localhost:8080"
    cd /d "%~dp0agent-system\webgpu"
    python -m http.server 8080
    goto start
)

if /i "%choice%"=="g" (
    echo.
    set /p gen_prompt="Describe what to build: "
    if not "%gen_prompt%"=="" (
        echo.
        echo  Generating code with %current_model%...
        ollama run qwen2.5-coder:14b "Generate production-ready code for: %gen_prompt%"
    )
    goto start
)

if /i "%choice%"=="a" (
    echo.
    set /p analyze_prompt="What to analyze: "
    if not "%analyze_prompt%"=="" (
        echo.
        echo  Analyzing with deepseek-r1:7b...
        ollama run deepseek-r1:7b "Analyze this code and provide: 1) Architecture 2) Issues 3) Recommendations: %analyze_prompt%"
    )
    goto start
)

if /i "%choice%"=="d" (
    echo.
    set /p debug_prompt="Describe the bug/error: "
    if not "%debug_prompt%"=="" (
        echo.
        echo  Debugging with deepseek-r1:7b...
        ollama run deepseek-r1:7b "Debug and fix: %debug_prompt%"
    )
    goto start
)

if /i "%choice%"=="b" (
    echo.
    set /p brain_prompt="What to discuss: "
    if not "%brain_prompt%"=="" (
        echo.
        echo  Brainstorming with deepseek-r1:7b...
        ollama run deepseek-r1:7b "Architectural discussion: %brain_prompt%"
    )
    goto start
)

if /i "%choice%"=="q" (
    echo.
    echo  Goodbye, Developer!
    echo  ═══════════════════════════════
    timeout /t 1 >nul
    exit
)

echo.
echo  Invalid option. Press Enter to continue...
pause >nul
goto start