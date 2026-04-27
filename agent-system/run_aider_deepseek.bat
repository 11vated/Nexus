@echo off
REM Aider Launcher - DeepSeek-R1 (Reasoning)
cd /d "%~dp0agent-system"
echo Starting Aider with DeepSeek-R1...
echo Model: deepseek-r1:7b
echo.
venv_aider\Scripts\aider.exe --config aider_deepseek.yaml --no-git
pause