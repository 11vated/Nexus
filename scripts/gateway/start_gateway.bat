@echo off
REM Start Nexus Unified Gateway on Windows
REM Usage: scripts\gateway\start_gateway.bat

echo Starting Nexus Unified Gateway...

REM Check if LiteLLM is installed
python -c "import litellm" 2>nul
if errorlevel 1 (
    echo Installing LiteLLM...
    pip install "litellm[proxy]"
)

REM Start LiteLLM gateway
echo Starting LiteLLM on port 4000...
python -m litellm --config gateway_config.yaml --port 4000

echo Gateway stopped.
pause