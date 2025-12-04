# Windows Installer - Requirements and Flow

## ⚠️ CRITICAL: .env File is REQUIRED

The `.env` file is **MANDATORY** for installation. The application cannot function without it.

### Why .env is Required

The .env file contains essential configuration that the application needs:

- **API Keys**: OPENAI_API_KEY or other LLM provider credentials
- **Database Configuration**: DB_PASSWORD, DATABASE_URL, DB_USERNAME, DB_HOST, DB_PORT, DB_NAME
- **Service URLs**: FASTAPI_URL, CHROMA_URL, REDIS_URL, OLLAMA_URL
- **Application Settings**: REQUEST_TIMEOUT, LOG_LEVEL, ENVIRONMENT

Without these values, the Docker containers cannot start, the database cannot connect, and the application will not run.

## Installation Flow with Required .env

### 1. Welcome Screen
- Click "Next" to begin

### 2. License Agreement
- Accept license terms
- Click "Next"

### 3. Environment Configuration (REQUIRED)
**User MUST select a .env file to proceed**

- **File Selection Box**: Shows path to selected .env file
- **Browse Button**: Opens file picker to select .env file
- **Next Button**: **DISABLED** until a valid file is selected
- **Required Content** displayed to user:
  ```
  Your .env file must contain:
  • OPENAI_API_KEY or other LLM provider keys
  • Database credentials (DB_PASSWORD, DATABASE_URL)
  • Service configuration (OLLAMA_URL, CHROMA_URL, etc.)

  Without this file, the application cannot function.
  ```

**The installer will NOT proceed past this screen without a .env file.**

### 4. Installation Directory
- Choose install location (default: `C:\Program Files\GenAI Research`)
- Click "Next" to start installation

### 5. Installation Progress
All steps run automatically with visible progress:

**Phase 1: File Installation (1 minute)**
- Copies application files
- Installs Python scripts
- Copies Docker configurations

**Phase 2: Environment Setup (5 seconds)**
- **Validates .env file exists and has content**
- Copies .env to installation directory
- Verifies file integrity
- **Installation FAILS if .env is invalid**

**Phase 3: System Configuration (10-20 minutes)**
- Detects GPU/CPU and RAM
- Downloads AI models based on hardware
- Builds Docker images (base-poetry-deps, then all services)
- **All output visible in installer progress window**

### 6. Completion
- Application is ready to use
- Launch from Start Menu

## .env File Validation

The installer performs multiple validation checks:

### Check 1: Dialog Level (CustomUI.wxs)
- Next button disabled if `ENV_FILE_PATH` is empty
- User cannot proceed without selecting a file

### Check 2: File Copy (Product.wxs - CopyEnvFile)
```powershell
if (-not (Test-Path '[ENV_FILE_PATH]')) {
    Write-Host 'ERROR: .env file not found'
    exit 1  # Installation FAILS
}
Copy-Item '[ENV_FILE_PATH]' '[INSTALLFOLDER].env' -Force
```

### Check 3: Setup Script (setup-during-install.ps1)
```powershell
# Verify .env file exists
if (-not (Test-Path $envFile)) {
    Write-Log "ERROR: .env file not found"
    throw ".env file is missing"  # Installation FAILS
}

# Validate .env file has content
$envContent = Get-Content $envFile -Raw
if (-not $envContent -or $envContent.Trim().Length -eq 0) {
    Write-Log "ERROR: .env file is empty"
    throw ".env file is empty"  # Installation FAILS
}
```

**At each check, if .env is invalid, the installation stops with a clear error message.**

## What Happens if .env is Missing?

### During Dialog
- User sees: "Select your .env configuration file. This file is REQUIRED..."
- Next button remains grayed out/disabled
- User cannot proceed

### If User Bypasses Dialog (shouldn't be possible)
- CopyEnvFile custom action fails
- Error message: "ERROR: .env file not found at [path]"
- Installation rolls back
- User sees error in installer log

### If .env Somehow Gets Deleted Before Setup
- setup-during-install.ps1 detects missing file
- Error message: "ERROR: .env file not found - this should have been copied"
- Installation fails gracefully
- User can retry with correct .env file

## Creating a Valid .env File

Users should create their .env file BEFORE running the installer.

### Minimum Required Content

```env
# OpenAI API Key (or other LLM provider)
OPENAI_API_KEY=sk-...your-key-here...

# Database Configuration
DATABASE_URL=postgresql://g3nA1-user:STRONG_PASSWORD@postgres:5432/rag_memory
DB_USERNAME=g3nA1-user
DB_PASSWORD=STRONG_PASSWORD
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
OLLAMA_URL=http://host.docker.internal:11434
LLM_OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_MODELS=llama3.1:8b

# Application Settings
REQUEST_TIMEOUT=600
LLM_TIMEOUT=300
LOG_LEVEL=INFO
ENVIRONMENT=production
ANONYMIZED_TELEMETRY=False

# LangSmith (optional)
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=dis-verification-genai
```

### Using the Template

The repository includes `.env.template` which users can:
1. Copy to `.env`
2. Edit with their actual values
3. Save and use during installation

```bash
# On the user's machine
cd path/to/download
cp .env.template .env
notepad .env  # Edit with actual values
```

## Installation Pre-Requisites Checklist

Before running the installer, users need:

- [ ] **Valid .env file with all required configuration**
- [ ] Docker Desktop installed and running
- [ ] Ollama installed (optional but recommended)
- [ ] 10GB+ free disk space
- [ ] Stable internet connection (for model downloads)
- [ ] Administrator privileges (for MSI installation)

## User Instructions

### Step 1: Prepare .env File
```
1. Download .env.template from the repository
2. Copy it to .env
3. Edit with your API keys and credentials
4. Save the file
```

### Step 2: Run Installer
```
1. Double-click dis-verification-genai-{VERSION}.msi
2. Accept license
3. Click "Browse..." and select your .env file
4. Choose installation directory
5. Click "Install"
6. Wait 10-20 minutes while installer configures everything
7. Click "Finish"
```

### Step 3: Launch Application
```
Start Menu → GenAI Research → GenAI Research
```

## Troubleshooting

### "Next button is disabled on .env screen"
- You haven't selected a .env file yet
- Click "Browse..." and select your .env file
- The path should appear in the text box
- Next button will enable automatically

### "Installation failed during environment setup"
- Your .env file may be invalid or empty
- Check that .env contains all required keys
- Ensure file is not corrupted
- Try re-running installer with a fresh .env file

### "Cannot copy .env file"
- Check file permissions on your .env file
- Ensure .env file still exists at the path you selected
- Make sure file is not open in another program
- Try copying .env to a simpler path (e.g., C:\Temp\.env)

## Summary

The .env file requirement ensures:
- ✅ **No silent failures**: User knows immediately if configuration is missing
- ✅ **Validation at multiple stages**: File is checked 3 times during installation
- ✅ **Clear error messages**: User knows exactly what's wrong
- ✅ **Application will work**: If installation completes, app has valid configuration
- ✅ **No post-install configuration**: Everything set up during installation

This is a **hard requirement** - there is no way to skip or bypass it, which is correct because the application cannot function without this configuration.
