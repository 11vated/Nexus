@echo off
REM ============================================================================
REM NEXUS VISION LAUNCHER
REM ============================================================================
REM Automatically uses vision model when images are detected
REM ============================================================================

echo.
echo +========================================+
echo ^|     NEXUS VISION AUTO-LAUNCHER    ^|
echo +========================================+
echo.

set "HAS_IMAGE=0"

REM Check for image files in arguments
echo %* | findstr /I ".png .jpg .jpeg .gif .bmp .webp" >nul
if %errorlevel%==0 set HAS_IMAGE=1

REM Check for screenshot/image keywords
echo %* | findstr /I "screenshot image photo see attached" >nul
if %errorlevel%==0 set HAS_IMAGE=1

if "%HAS_IMAGE%"=="1" (
    echo [VISION MODE DETECTED]
    echo Using llava for image analysis...
    echo.
    ollama run llava %*
) else (
    echo [TEXT MODE]
    echo Using qwen2.5-coder:14b...
    echo.
    ollama run qwen2.5-coder:14b %*
)

echo.
echo +========================================+