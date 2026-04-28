@echo off
REM Nexus Final Verification (Windows)
REM Usage: scripts\verify.bat

echo === Nexus Final Verification (Windows) ===

echo [1/4] Checking imports...
py -3.12 -c "from src.nexus.swe_bench import *; from src.nexus.gateway.client import *; print('Imports OK')"
if %errorlevel% neq 0 (
    echo FAIL: Import check failed
    exit /b 1
)
echo PASS: Imports OK

echo [2/4] Running core tests...
py -3.12 -m pytest tests/integration/test_swebench.py tests/unit/test_patch_selector.py tests/integration/test_subprocess.py -v -q --tb=no
if %errorlevel% neq 0 (
    echo FAIL: Core tests failed
    exit /b 1
)
echo PASS: Core tests OK

echo [3/4] Checking for shell=True...
py -3.12 -c "import subprocess, glob; found = any('shell=True' in open(f).read() for f in glob.glob('src/**/*.py')); exit(1 if found else 0)"
if %errorlevel% neq 0 (
    echo FAIL: Found shell=True - security risk
    exit /b 1
)
echo PASS: No shell=True

echo [4/4] Checking gateway config...
if not exist gateway_config.yaml (
    echo FAIL: gateway_config.yaml missing
    exit /b 1
)
echo PASS: Gateway config exists

echo.
echo ========================================
echo All checks passed. Nexus is ready.
echo ========================================
echo.
echo To start gateway:
echo   py -3.12 -m litellm --config gateway_config.yaml --port 4000
echo.
echo To run SWE-bench:
echo   py -3.12 -m nexus.cli swebench issue.txt --repo ./repo

pause