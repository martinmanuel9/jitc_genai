###############################################################################
# Windows Environment Setup Script
# Simple configuration wizard - only prompts for API keys
# All other settings use pre-configured defaults from .env.template
###############################################################################

param(
    [string]$InstallDir = "$env:ProgramFiles\GenAI Research"
)

$ErrorActionPreference = "Continue"

# Colors
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
    Write-Host ""
}

$EnvFile = Join-Path $InstallDir ".env"
$EnvTemplate = Join-Path $InstallDir ".env.template"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host "         GenAI Research - Environment Setup"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

# Create .env from template if it doesn't exist, or use existing
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvTemplate) {
        Copy-Item $EnvTemplate $EnvFile -Force
        Write-Success "Created .env from template with default settings"
    } else {
        Write-ErrorMsg "Template file not found: $EnvTemplate"
        exit 1
    }
} else {
    Write-Info "Using existing .env file"
}

Write-Header "API Keys Configuration"
Write-Info "All other settings are pre-configured with working defaults."
Write-Host ""

# OpenAI API Key
Write-Info "OpenAI API Key (required for cloud models like GPT-4, GPT-4o)"
$openaiKey = Read-Host "Enter OpenAI API Key (press Enter to skip)"
if ($openaiKey) {
    (Get-Content $EnvFile) -replace '^OPENAI_API_KEY=.*', "OPENAI_API_KEY=$openaiKey" | Set-Content $EnvFile
    Write-Success "OpenAI API key configured"
} else {
    Write-Warning "OpenAI API key not configured"
    Write-Info "You can use local Ollama models instead, or add the key later to .env"
}

Write-Host ""

# LangSmith (Optional)
Write-Info "LangSmith API Key (optional - for debugging and monitoring)"
$langsmithKey = Read-Host "Enter LangSmith API Key (press Enter to skip)"
if ($langsmithKey) {
    $langsmithProject = Read-Host "Enter LangSmith project name"
    (Get-Content $EnvFile) -replace '^LANGCHAIN_API_KEY=.*', "LANGCHAIN_API_KEY=$langsmithKey" | Set-Content $EnvFile
    (Get-Content $EnvFile) -replace '^LANGSMITH_PROJECT=.*', "LANGSMITH_PROJECT=$langsmithProject" | Set-Content $EnvFile
    (Get-Content $EnvFile) -replace '^LANGSMITH_TRACING=.*', 'LANGSMITH_TRACING=true' | Set-Content $EnvFile
    Write-Success "LangSmith tracing enabled"
} else {
    Write-Info "LangSmith tracing disabled (can be enabled later in .env)"
}

Write-Header "Ollama (Local LLM Support)"

$ollamaInstalled = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaInstalled) {
    Write-Success "Ollama is installed"
} else {
    Write-Warning "Ollama is NOT installed"
    Write-Host ""
    Write-Host "To install Ollama for local model support:"
    Write-Host "  Download from: https://ollama.com/download/windows"
}

Write-Host ""
Write-Host "After installing Ollama, you must manually start the server and pull models:"
Write-Host ""
Write-Host "  1. Start Ollama server (in PowerShell):"
Write-Host "     `$env:OLLAMA_HOST='0.0.0.0:11434'; ollama serve"
Write-Host ""
Write-Host "  2. In a NEW PowerShell window, pull models:"
Write-Host ""
Write-Host "     # Pull recommended text models for chat/generation (~9 GB)" -ForegroundColor DarkGray
Write-Host "     & `"$InstallDir\scripts\pull-ollama-models.ps1`" -Mode recommended" -ForegroundColor Gray
Write-Host ""
Write-Host "     # Pull vision models for image understanding (~14.5 GB)" -ForegroundColor DarkGray
Write-Host "     # Includes: granite3.2-vision:2b, llava:7b, llava:13b" -ForegroundColor DarkGray
Write-Host "     & `"$InstallDir\scripts\pull-ollama-models.ps1`" -Mode vision" -ForegroundColor Gray
Write-Host ""
Write-Info "See $InstallDir\INSTALL.md for detailed instructions."

Write-Header "Setup Complete"

Write-Success "Environment configuration completed!"
Write-Host ""
Write-Host "Configuration file: $EnvFile"
Write-Host ""
Write-Info "Pre-configured services (ready to use):"
Write-Host "  - FastAPI Backend: http://localhost:9020"
Write-Host "  - Streamlit Web UI: http://localhost:8501"
Write-Host "  - PostgreSQL: localhost:5432"
Write-Host "  - ChromaDB: localhost:8001"
Write-Host "  - Redis: localhost:6379"
if ($ollamaInstalled) {
    Write-Host "  - Ollama: http://localhost:11434"
}

Write-Host ""
Write-Info "To start the application:"
Write-Host "  cd `"$InstallDir`""
Write-Host "  docker compose up -d"
Write-Host ""
Write-Info "Or use the Start Menu shortcut: GenAI Research"
Write-Host ""
