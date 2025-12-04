@echo off
:: GenAI Research - Download AI Models
:: Double-click this file to download recommended AI models for Ollama
::
:: This batch file runs the PowerShell script with the correct execution policy

title GenAI Research - Downloading AI Models

:: Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"

:: Run the PowerShell script
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%Download-AI-Models.ps1"
