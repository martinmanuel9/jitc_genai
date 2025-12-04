###############################################################################
# GenAI Research - Download AI Models & Start Services
#
# Double-click this script to:
#   1. Check/Start Docker containers
#   2. Download recommended AI models for Ollama
#
# This script will download:
#   - Text models for chat and analysis
#   - Embedding models for RAG (document search)
#   - Vision models for image/document analysis
#
###############################################################################

# Keep window open and show what we're doing
$Host.UI.RawUI.WindowTitle = "GenAI Research - Setup & Download Models"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "       GenAI Research - Setup & Model Downloader" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Detect install directory (script location or default)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Split-Path -Parent $ScriptDir

# Check if we're in a valid install directory
if (-not (Test-Path "$InstallDir\docker-compose.yml")) {
    # Try default location
    if (Test-Path "C:\Program Files\GenAI Research\docker-compose.yml") {
        $InstallDir = "C:\Program Files\GenAI Research"
    } else {
        Write-Host "[WARNING] Could not find GenAI Research installation directory." -ForegroundColor Yellow
        Write-Host "Docker services will be skipped." -ForegroundColor Yellow
        $InstallDir = $null
    }
}

if ($InstallDir) {
    Write-Host "[INFO] Install directory: $InstallDir" -ForegroundColor Cyan
    Write-Host ""
}

###############################################################################
# STEP 1: Check Docker Desktop
###############################################################################
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       Step 1: Checking Docker Desktop" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerInstalled) {
    Write-Host "[ERROR] Docker is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "[OK] Docker is installed" -ForegroundColor Green

# Check if Docker is running
$dockerRunning = $false
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
    }
} catch {}

if (-not $dockerRunning) {
    Write-Host "[INFO] Docker Desktop is not running. Attempting to start..." -ForegroundColor Yellow

    # Try to start Docker Desktop
    $dockerDesktopPaths = @(
        "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )

    $dockerStarted = $false
    foreach ($path in $dockerDesktopPaths) {
        if (Test-Path $path) {
            Write-Host "[INFO] Starting Docker Desktop from: $path" -ForegroundColor Cyan
            Start-Process $path
            $dockerStarted = $true
            break
        }
    }

    if ($dockerStarted) {
        Write-Host "[INFO] Waiting for Docker to start (this may take 30-60 seconds)..." -ForegroundColor Yellow
        $maxWait = 120
        $waited = 0
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 5
            $waited += 5

            try {
                $dockerInfo = docker info 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $dockerRunning = $true
                    Write-Host "[OK] Docker Desktop is now running" -ForegroundColor Green
                    break
                }
            } catch {}

            Write-Host "  Waiting... ($waited/$maxWait seconds)" -ForegroundColor Gray
        }

        if (-not $dockerRunning) {
            Write-Host "[ERROR] Docker Desktop did not start in time." -ForegroundColor Red
            Write-Host "Please start Docker Desktop manually and try again." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Press any key to exit..."
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            exit 1
        }
    } else {
        Write-Host "[ERROR] Could not find Docker Desktop executable." -ForegroundColor Red
        Write-Host "Please start Docker Desktop manually and try again." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}

Write-Host "[OK] Docker Desktop is running" -ForegroundColor Green
Write-Host ""

###############################################################################
# STEP 2: Start Docker Containers
###############################################################################
if ($InstallDir) {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "       Step 2: Starting Docker Containers" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    Set-Location $InstallDir

    # Check if containers are already running
    $runningContainers = docker compose ps --status running --format "{{.Name}}" 2>&1
    $containerCount = ($runningContainers | Measure-Object -Line).Lines

    if ($containerCount -gt 0) {
        Write-Host "[OK] Docker containers are already running ($containerCount containers)" -ForegroundColor Green
        Write-Host ""
        docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>&1
        Write-Host ""
    } else {
        Write-Host "[INFO] Starting Docker containers..." -ForegroundColor Yellow
        Write-Host ""

        # Check if images need to be built
        $images = docker images --format "{{.Repository}}" 2>&1
        $needsBuild = $true

        foreach ($img in $images) {
            if ($img -match "genai" -or $img -match "fastapi" -or $img -match "streamlit") {
                $needsBuild = $false
                break
            }
        }

        if ($needsBuild) {
            Write-Host "[INFO] Building Docker images (first time setup - this may take 10-20 minutes)..." -ForegroundColor Yellow
            Write-Host ""

            # Build base-poetry-deps first
            Write-Host ">>> Building base-poetry-deps..." -ForegroundColor Cyan
            docker compose build base-poetry-deps 2>&1 | ForEach-Object { Write-Host $_ }

            if ($LASTEXITCODE -ne 0) {
                Write-Host "[ERROR] Failed to build base-poetry-deps" -ForegroundColor Red
                Write-Host "Press any key to continue anyway..."
                $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            }

            Write-Host ""
            Write-Host ">>> Building application services..." -ForegroundColor Cyan
            docker compose build 2>&1 | ForEach-Object { Write-Host $_ }

            if ($LASTEXITCODE -ne 0) {
                Write-Host "[ERROR] Failed to build application services" -ForegroundColor Red
                Write-Host "Press any key to continue anyway..."
                $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            }
            Write-Host ""
        }

        # Start containers
        Write-Host "[INFO] Starting services with docker compose up -d..." -ForegroundColor Yellow
        docker compose up -d 2>&1 | ForEach-Object { Write-Host $_ }

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[OK] Docker containers started successfully!" -ForegroundColor Green

            # Wait for services to initialize
            Write-Host "[INFO] Waiting 15 seconds for services to initialize..." -ForegroundColor Yellow
            Start-Sleep -Seconds 15

            # Show status
            Write-Host ""
            Write-Host "Container Status:" -ForegroundColor Cyan
            docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>&1
        } else {
            Write-Host "[ERROR] Failed to start containers" -ForegroundColor Red
            Write-Host "You may need to run this script as Administrator or check Docker Desktop." -ForegroundColor Yellow
        }
        Write-Host ""
    }
}

###############################################################################
# STEP 3: Check Ollama
###############################################################################
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       Step 3: Checking Ollama" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "[WARNING] Ollama is not installed!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ollama is required for local AI models." -ForegroundColor Yellow
    Write-Host "Please install Ollama from: https://ollama.com/download/windows" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "After installing Ollama, run this script again to download models." -ForegroundColor Yellow
    Write-Host ""

    if ($InstallDir) {
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "  Docker services are running!" -ForegroundColor Green
        Write-Host "  Access the web interface at: http://localhost:8501" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host ""
    }

    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 0
}

Write-Host "[OK] Ollama is installed" -ForegroundColor Green
Write-Host ""

# Check if Ollama is running
Write-Host "Checking if Ollama is running..." -ForegroundColor Cyan
$ollamaRunning = $false
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5 -ErrorAction Stop
    $ollamaRunning = $true
    Write-Host "[OK] Ollama is running" -ForegroundColor Green
} catch {
    Write-Host "[INFO] Starting Ollama..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3

    # Check again
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5 -ErrorAction Stop
        $ollamaRunning = $true
        Write-Host "[OK] Ollama is now running" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Could not start Ollama. Please start it manually and try again." -ForegroundColor Red
        Write-Host ""
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}

Write-Host ""

###############################################################################
# STEP 4: Download AI Models
###############################################################################
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       Step 4: Downloading AI Models" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This may take 10-30 minutes depending on your internet speed." -ForegroundColor Yellow
Write-Host ""

# Function to pull a model
function Pull-Model {
    param(
        [string]$ModelName,
        [string]$Description,
        [string]$Size
    )

    Write-Host ""
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "Downloading: $ModelName" -ForegroundColor Cyan
    Write-Host "  $Description ($Size)" -ForegroundColor Gray
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

    $process = Start-Process -FilePath "ollama" -ArgumentList "pull", $ModelName -NoNewWindow -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Host "[SUCCESS] $ModelName downloaded" -ForegroundColor Green
        return $true
    } else {
        Write-Host "[FAILED] Could not download $ModelName" -ForegroundColor Red
        return $false
    }
}

$successCount = 0
$failCount = 0

# ============================================================
# TEXT MODELS - For chat and analysis
# ============================================================
Write-Host ""
Write-Host ">>> TEXT MODELS <<<" -ForegroundColor Yellow
Write-Host ""

if (Pull-Model "llama3.2:3b" "Meta Llama 3.2 - Fast and efficient" "2 GB") { $successCount++ } else { $failCount++ }
if (Pull-Model "llama3.1:8b" "Meta Llama 3.1 - Powerful general model" "4.7 GB") { $successCount++ } else { $failCount++ }
if (Pull-Model "phi3:mini" "Microsoft Phi-3 - Efficient reasoning" "2.3 GB") { $successCount++ } else { $failCount++ }

# ============================================================
# EMBEDDING MODELS - Required for RAG (document search)
# ============================================================
Write-Host ""
Write-Host ">>> EMBEDDING MODELS (Required for RAG) <<<" -ForegroundColor Yellow
Write-Host ""

if (Pull-Model "snowflake-arctic-embed2" "Snowflake Arctic Embed v2 - Document embeddings" "1.7 GB") { $successCount++ } else { $failCount++ }

# ============================================================
# VISION MODELS - For image and document analysis
# ============================================================
Write-Host ""
Write-Host ">>> VISION MODELS <<<" -ForegroundColor Yellow
Write-Host ""

if (Pull-Model "granite3.2-vision:2b" "IBM Granite Vision - Lightweight multimodal" "1.5 GB") { $successCount++ } else { $failCount++ }
if (Pull-Model "llava:7b" "LLaVA 1.6 7B - Vision-language model" "4.7 GB") { $successCount++ } else { $failCount++ }
if (Pull-Model "llava:13b" "LLaVA 1.6 13B - Larger multimodal" "8 GB") { $successCount++ } else { $failCount++ }

###############################################################################
# SUMMARY
###############################################################################
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "       Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

if ($InstallDir) {
    Write-Host "  Docker Services: RUNNING" -ForegroundColor Green
}
Write-Host "  Models downloaded: $successCount" -ForegroundColor Green
if ($failCount -gt 0) {
    Write-Host "  Models failed: $failCount" -ForegroundColor Red
}
Write-Host ""

# Show installed models
Write-Host "Installed Ollama models:" -ForegroundColor Cyan
Write-Host ""
ollama list
Write-Host ""

Write-Host "============================================================" -ForegroundColor Green
Write-Host "  GenAI Research is ready to use!" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "  Web Interface: http://localhost:8501" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to close this window..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
