@echo off
REM Aider Launcher - Qwen2.5-Coder (Code Generation)
cd /d "%~dp0agent-system"
echo Starting Aider with Qwen2.5-Coder...
echo Model: qwen2.5-coder:7b
echo.
venv_aider\Scripts\aider.exe --config aider_qwen.yaml --no-git
pause