###############################################################################
# Create .env file from installer input
# Called by WIX custom action during installation
###############################################################################

param(
    [string]$InstallDir = "$env:ProgramFiles\GenAI Research",
    [string]$EnvContent = ""
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $logFile = Join-Path $env:TEMP "dis-genai-install.log"
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $Message" | Out-File -FilePath $logFile -Append
}

try {
    Write-Log "Starting .env file creation"
    Write-Log "Install Directory: $InstallDir"

    $envFile = Join-Path $InstallDir ".env"

    if ($EnvContent -and $EnvContent.Trim() -ne "") {
        # User provided .env content during installation
        Write-Log "Creating .env file from user-provided content"

        # Decode if needed (WIX might pass base64 encoded content)
        try {
            $decoded = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($EnvContent))
            $EnvContent = $decoded
            Write-Log "Decoded base64 content"
        } catch {
            # Not base64, use as-is
            Write-Log "Using content as plain text"
        }

        # Write the content to .env file
        Set-Content -Path $envFile -Value $EnvContent -Force
        Write-Log ".env file created successfully from user input"

    } else {
        # No content provided, copy from template
        Write-Log "No user content provided, copying from template"

        $templateFile = Join-Path $InstallDir ".env.template"
        if (Test-Path $templateFile) {
            Copy-Item -Path $templateFile -Destination $envFile -Force
            Write-Log ".env file created from template"
        } else {
            Write-Log "WARNING: Template file not found at $templateFile"
            # Create a minimal .env file
            $minimalEnv = @"
# GenAI Research - Environment Configuration
# This file was auto-generated. Please configure it before running the application.

# OpenAI API Key
OPENAI_API_KEY=

# Database Configuration
DATABASE_URL=postgresql://g3nA1-user:CHANGE_ME@postgres:5432/rag_memory
DB_USERNAME=g3nA1-user
DB_PASSWORD=CHANGE_ME
DB_HOST=postgres
DB_PORT=5432
DB_NAME=rag_memory

# Service URLs
FASTAPI_URL=http://fastapi:9020
CHROMA_URL=http://chromadb:8001
CHROMA_HOST=chromadb
CHROMA_PORT=8001
REDIS_URL=redis://redis:6379/0
REDIS_HOST=redis
REDIS_PORT=6379

# Ollama Configuration
OLLAMA_MODELS=
OLLAMA_URL=http://host.docker.internal:11434
LLM_OLLAMA_HOST=http://host.docker.internal:11434

# Application Configuration
REQUEST_TIMEOUT=600
LLM_TIMEOUT=300
LOG_LEVEL=INFO
ENVIRONMENT=production
ANONYMIZED_TELEMETRY=False

# LangSmith Tracing
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=dis-verification-genai
"@
            Set-Content -Path $envFile -Value $minimalEnv -Force
            Write-Log "Created minimal .env file"
        }
    }

    # Validate the .env file was created
    if (Test-Path $envFile) {
        $fileSize = (Get-Item $envFile).Length
        Write-Log ".env file created successfully (Size: $fileSize bytes)"
        exit 0
    } else {
        Write-Log "ERROR: .env file was not created"
        exit 1
    }

} catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    Write-Log "Stack trace: $($_.ScriptStackTrace)"
    exit 1
}
