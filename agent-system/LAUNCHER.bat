@echo off
REM Ultimate Agent Launcher - All Local Models (No API Keys!)
REM Switch between any Ollama model instantly

:menu
cls
echo ================================================
echo    ULTIMATE AGENT LAUNCHER (Local - Full Access)
echo ================================================
echo.
echo Available Models (all local, no API keys):
echo.
echo [1] Qwen2.5-Coder 14B  ^(BEST for Code^)
echo [2] Qwen2.5-Coder 7B   ^(Stable^)
echo [3] DeepSeek-R1 7B     ^(Reasoning/Planning^)
echo [4] DeepSeek-R1 1.5B   ^(Fast Reasoning^)
echo [5] Gemma 4 26B        ^(Google Large^)
echo [6] CodeLlama          ^(Meta Code^)
echo [7] Mistral 7B         ^(Fast^)
echo [8] Llama 3.1 8B       ^(Meta^)
echo.
echo --- AGENTS ---
echo [O] OpenCode
echo [A] Aider
echo [G] Goose Desktop
echo.
echo [Q] Quit
echo.
echo ================================================
set /p choice="Select model (1-8) or agent (O/A/G): "

if /i "%choice%"=="1" set MODEL=qwen2.5-coder:14b & goto agent
if /i "%choice%"=="2" set MODEL=qwen2.5-coder:7b & goto agent
if /i "%choice%"=="3" set MODEL=deepseek-r1:7b & goto agent
if /i "%choice%"=="4" set MODEL=deepseek-r1:1.5b & goto agent
if /i "%choice%"=="5" set MODEL=gemma4:26b & goto agent
if /i "%choice%"=="6" set MODEL=codellama:latest & goto agent
if /i "%choice%"=="7" set MODEL=mistral:7b & goto agent
if /i "%choice%"=="8" set MODEL=llama3.1:8b & goto agent
if /i "%choice%"=="Q" exit

:agent
cls
echo Model: %MODEL%
echo.
echo [1] OpenCode
echo [2] Aider  
echo [3] Goose Desktop
echo [4] Back to model selection
echo.
set /p agent="Select agent (1-4): "

if "%agent%"=="1" goto opencode
if "%agent%"=="2" goto aider
if "%agent%"=="3" goto goose
if "%agent%"=="4" goto menu

:opencode
echo Starting OpenCode with %MODEL%...
timeout /t 1 /nobreak >nul
opencode --model ollama/%MODEL%
goto menu

:aider
echo Starting Aider with %MODEL%...
cd agent-system
call venv_aider\Scripts\aider.exe --config aider_ultimate.yaml --no-git --model ollama/%MODEL%
goto menu

:goose
echo Starting Goose Desktop...
start "" "%USERPROFILE%\Desktop\Goose-win32-x64\dist-windows\Goose.exe"
echo Note: Goose uses default model from config. Edit config to change.
timeout /t 2 >nul
goto menu