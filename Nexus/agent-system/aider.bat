@echo off
REM Aider Launcher - Execute with Ollama
cd /d "%~dp0agent-system"
echo Running task: %*
call venv_aider\Scripts\aider.exe --config aider_config.yaml --no-git --message "%*"