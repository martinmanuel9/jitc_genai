@echo off
REM ============================================================================
REM GenAI Research - Setup Launcher
REM This batch file launches the PowerShell setup script in a visible window
REM ============================================================================

title GenAI Research Setup - DO NOT CLOSE THIS WINDOW

echo.
echo ============================================================================
echo   GenAI Research - Setup Starting
echo ============================================================================
echo.
echo   This window will show the installation progress.
echo   Please DO NOT close this window until setup is complete.
echo.
echo ============================================================================
echo.

cd /d "%~dp0.."

REM Run the PowerShell setup script
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-during-install.ps1" -InstallDir "%~dp0.."

REM Capture the exit code
set PS_EXIT_CODE=%ERRORLEVEL%

REM Always pause at the end so user can see any errors
echo.
echo ============================================================================
if %PS_EXIT_CODE% EQU 0 (
    echo   Setup completed. You may close this window.
) else (
    echo   Setup encountered an error. Please review the messages above.
)
echo ============================================================================
echo.
pause
