@echo off
REM Nexus Unified Gateway Startup (Windows)
REM Usage: scripts\gateway\start_gateway.bat

echo === Starting Nexus Unified Gateway ===
echo.

REM Check Python 3.12
echo Checking Python 3.12...
py -3.12 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3.12 not found. Please install from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo OK: Python 3.12 found

REM Check LiteLLM
echo Checking LiteLLM...
py -3.12 -c "import litellm" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing LiteLLM...
    py -3.12 -m pip install "litellm[proxy]" --quiet
)
echo OK: LiteLLM installed

REM Check for optional llama.cpp server (GGUF models)
echo.
echo NOTE: To use GGUF models, start llama.cpp server first:
echo   llama-server.exe -m models\qwen2.5-coder-14b-q4_K_M.gguf --port 8080
echo.

REM Check gateway config
if not exist gateway_config.yaml (
    echo ERROR: gateway_config.yaml not found
    pause
    exit /b 1
)
echo OK: gateway_config.yaml found

echo.
echo Starting LiteLLM Gateway on port 4000...
echo Press Ctrl+C to stop
echo.
py -3.12 -m litellm --config gateway_config.yaml --port 4000

pause