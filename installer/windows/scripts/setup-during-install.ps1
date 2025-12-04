###############################################################################
# Setup Script for WiX Installer
# Runs in a VISIBLE PowerShell window during MSI installation
# Output is shown in real-time AND logged to file for debugging
#
# EXIT CODES: 0 = Success, 1 = Failure
###############################################################################

param(
    [string]$InstallDir = "$env:ProgramFiles\GenAI Research"
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# Global flag to track if we should wait for user at the end
$script:WaitForUserAtEnd = $true

# Function to wait for user input (works in all PowerShell contexts)
function Wait-ForUserInput {
    param([string]$Message = "Press Enter to continue...")
    Write-Host ""
    Write-Host $Message -ForegroundColor Yellow
    # Use Read-Host which works in all contexts (unlike RawUI.ReadKey)
    Read-Host
}

# Setup logging - save to installation directory logs folder
$LogDir = Join-Path $InstallDir "logs"
$LogFile = $null
$StartTime = Get-Date

# Try to create log directory and file
try {
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
    $LogFile = Join-Path $LogDir "install-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
    # Test we can write to the log file
    Set-Content -Path $LogFile -Value "GenAI Research Installation Log - $(Get-Date)" -ErrorAction Stop
    Write-Host "[INFO] Log file created: $LogFile" -ForegroundColor Cyan
} catch {
    # Fallback to temp directory if we can't write to install dir
    $LogDir = $env:TEMP
    $LogFile = Join-Path $LogDir "genai-install-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
    try {
        Set-Content -Path $LogFile -Value "GenAI Research Installation Log - $(Get-Date)" -ErrorAction Stop
        Write-Host "[WARNING] Could not write to install directory, using temp: $LogFile" -ForegroundColor Yellow
    } catch {
        $LogFile = $null
        Write-Host "[WARNING] Could not create log file, continuing without logging" -ForegroundColor Yellow
    }
}

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"

    # Write to console with color
    Write-Host $logMessage -ForegroundColor $Color

    # Write to log file if available
    if ($LogFile) {
        Add-Content -Path $LogFile -Value $logMessage -ErrorAction SilentlyContinue
    }
}

function Write-LogSuccess {
    param([string]$Message)
    Write-Log "[SUCCESS] $Message" -Color Green
}

function Write-LogError {
    param([string]$Message)
    Write-Log "[ERROR] $Message" -Color Red
}

function Write-LogWarning {
    param([string]$Message)
    Write-Log "[WARNING] $Message" -Color Yellow
}

function Write-LogStep {
    param([string]$Message)
    Write-Host ""
    Write-Log "=============================================="
    Write-Log $Message -Color Cyan
    Write-Log "=============================================="
    Write-Host ""
}

###############################################################################
# Set console appearance for maximum visibility
###############################################################################
try {
    # Set window title
    $host.UI.RawUI.WindowTitle = "GenAI Research - Installation Progress - DO NOT CLOSE"

    # Set colors for high visibility
    $host.UI.RawUI.BackgroundColor = "DarkBlue"
    $host.UI.RawUI.ForegroundColor = "White"

    # Try to maximize window and set buffer size
    try {
        $maxSize = $host.UI.RawUI.MaxPhysicalWindowSize
        $host.UI.RawUI.WindowSize = New-Object System.Management.Automation.Host.Size($maxSize.Width, $maxSize.Height)
        $host.UI.RawUI.BufferSize = New-Object System.Management.Automation.Host.Size($maxSize.Width, 9999)
    } catch { }

    Clear-Host
} catch { }

###############################################################################
# Header - Large and prominent
###############################################################################
Write-Host ""
Write-Host ""
Write-Host "    ╔════════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "    ║                                                                                ║" -ForegroundColor Green
Write-Host "    ║                    GENAI RESEARCH - INSTALLATION IN PROGRESS                   ║" -ForegroundColor Green
Write-Host "    ║                                                                                ║" -ForegroundColor Green
Write-Host "    ╠════════════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "    ║                                                                                ║" -ForegroundColor Cyan
Write-Host "    ║   This window shows REAL-TIME installation progress. You will see:            ║" -ForegroundColor Cyan
Write-Host "    ║                                                                                ║" -ForegroundColor Cyan
Write-Host "    ║      • File verification and setup                                             ║" -ForegroundColor Cyan
Write-Host "    ║      • Docker image builds - this takes 10-20 minutes                           ║" -ForegroundColor Cyan
Write-Host "    ║      • Container startup and health checks                                     ║" -ForegroundColor Cyan
Write-Host "    ║      • Service verification                                                    ║" -ForegroundColor Cyan
Write-Host "    ║                                                                                ║" -ForegroundColor Cyan
Write-Host "    ╠════════════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "    ║                                                                                ║" -ForegroundColor Yellow
Write-Host "    ║   ██  DO NOT CLOSE THIS WINDOW - Installation will fail if closed!  ██        ║" -ForegroundColor Yellow
Write-Host "    ║                                                                                ║" -ForegroundColor Yellow
Write-Host "    ╚════════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host ""

Write-Log "Install Directory: $InstallDir"
if ($LogFile) {
    Write-Log "Log File: $LogFile"
}
Write-Host ""

###############################################################################
# STEP 0: Verify Installation Directory Contents
###############################################################################
Write-LogStep "STEP 0/7: Verifying Installation Directory"

Write-Log "Checking installation directory: $InstallDir"

if (-not (Test-Path $InstallDir)) {
    Write-LogError "Installation directory does not exist: $InstallDir"
    Write-LogError "This is a critical error - the MSI did not install files correctly."
    Wait-ForUserInput "Press Enter to exit..."
    exit 1
}

# Check for critical files
$criticalFiles = @(
    "docker-compose.yml",
    "Dockerfile.base",
    "pyproject.toml",
    "VERSION"
)

$missingFiles = @()
foreach ($file in $criticalFiles) {
    $filePath = Join-Path $InstallDir $file
    if (Test-Path $filePath) {
        Write-LogSuccess "Found: $file"
    } else {
        Write-LogError "MISSING: $file"
        $missingFiles += $file
    }
}

# Check for critical directories
$criticalDirs = @("src", "scripts")
foreach ($dir in $criticalDirs) {
    $dirPath = Join-Path $InstallDir $dir
    if (Test-Path $dirPath) {
        $fileCount = (Get-ChildItem -Path $dirPath -Recurse -File).Count
        Write-LogSuccess "Found: $dir/ - $fileCount files"
    } else {
        Write-LogError "MISSING: $dir/"
        $missingFiles += "$dir/"
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Host ""
    Write-LogError "Critical files are missing from the installation!"
    Write-LogError "Missing: $($missingFiles -join ', ')"
    Write-Host ""
    Write-Log "This usually means:"
    Write-Log "  1. The MSI installer was built incorrectly"
    Write-Log "  2. The installation was interrupted"
    Write-Log "  3. Antivirus software blocked file extraction"
    Write-Host ""
    Write-Log "Please try:"
    Write-Log "  1. Uninstall the application from Add/Remove Programs"
    Write-Log "  2. Download a fresh copy of the installer"
    Write-Log "  3. Temporarily disable antivirus during installation"
    Write-Log "  4. Run the installer as Administrator"
    Wait-ForUserInput "Press Enter to exit..."
    exit 1
}

Write-LogSuccess "All critical files verified"

###############################################################################
# STEP 1: Verify .env File
###############################################################################
Write-LogStep "STEP 1/7: Verifying .env File"

$envFile = Join-Path $InstallDir ".env"

if (-not (Test-Path $envFile)) {
    Write-LogWarning ".env file not found at: $envFile"
    Write-Host ""
    Write-Log "The .env file was not copied during installation."
    Write-Log "This can happen if the source path contained spaces or special characters."
    Write-Host ""

    # Prompt user to provide the .env file path
    $maxAttempts = 3
    $attempt = 0
    $envCopied = $false

    while ($attempt -lt $maxAttempts -and -not $envCopied) {
        $attempt++
        Write-Host ""
        Write-Log "Please enter the full path to your .env file:" -Color Yellow
        Write-Host "  Example: C:\Users\YourName\Downloads\.env" -ForegroundColor Gray
        Write-Host ""
        $userEnvPath = Read-Host "  .env file path"

        if ([string]::IsNullOrWhiteSpace($userEnvPath)) {
            Write-LogError "No path entered. Attempt $attempt of $maxAttempts"
            continue
        }

        # Remove any surrounding quotes the user might have added
        $userEnvPath = $userEnvPath.Trim('"', "'", ' ')

        if (Test-Path $userEnvPath) {
            Write-Log "Found file: $userEnvPath"
            Write-Log "Copying to installation directory..."

            try {
                Copy-Item -Path $userEnvPath -Destination $envFile -Force -ErrorAction Stop
                Write-LogSuccess ".env file copied successfully!"
                $envCopied = $true
            } catch {
                Write-LogError "Failed to copy file: $_"
                Write-Log "Attempt $attempt of $maxAttempts"
            }
        } else {
            Write-LogError "File not found: $userEnvPath"
            Write-Log "Attempt $attempt of $maxAttempts"
        }
    }

    if (-not $envCopied) {
        Write-Host ""
        Write-LogError "Could not obtain .env file after $maxAttempts attempts."
        Write-Host ""
        Write-Log "To fix this manually:"
        Write-Log "1. Copy your .env file to: $envFile"
        Write-Log "2. Run 'First-Time Setup' from the Start Menu"
        Wait-ForUserInput "Press Enter to exit..."
        exit 1
    }
}

# Verify .env file content
$envContent = Get-Content $envFile -Raw
if (-not $envContent -or $envContent.Trim().Length -eq 0) {
    Write-LogError ".env file is empty"
    Wait-ForUserInput "Press Enter to exit..."
    exit 1
}

$lineCount = (Get-Content $envFile | Measure-Object -Line).Lines
Write-LogSuccess ".env file verified - $lineCount lines"

###############################################################################
# STEP 2: Verify Docker
###############################################################################
Write-LogStep "STEP 2/7: Checking Docker Desktop"

# First, check if Docker is installed
Write-Log "Checking if Docker Desktop is installed..."

$dockerInstalled = $false
$dockerExePath = $null

# Common Docker Desktop installation paths
$dockerPaths = @(
    "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
)

foreach ($path in $dockerPaths) {
    if (Test-Path $path) {
        $dockerInstalled = $true
        if ($path -like "*Docker Desktop.exe") {
            $dockerExePath = $path
        }
        break
    }
}

# Also check if docker command is available in PATH
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    $dockerInstalled = $true
}

if (-not $dockerInstalled) {
    Write-LogError "Docker Desktop is NOT INSTALLED!"
    Write-Host ""
    Write-LogError "Docker Desktop is required to run GenAI Research."
    Write-Host ""
    Write-Log "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    Write-Host ""
    Write-Log "After installing Docker Desktop:"
    Write-Log "1. Restart your computer"
    Write-Log "2. Run 'First-Time Setup' from the Start Menu"
    Wait-ForUserInput "Press Enter to exit..."
    exit 1
}

Write-LogSuccess "Docker Desktop is installed"

# Now check if Docker is running
Write-Log "Checking if Docker is running..."

$dockerRunning = $false
try {
    $dockerInfo = docker info 2>&1
    $dockerRunning = ($LASTEXITCODE -eq 0)
} catch {
    $dockerRunning = $false
}

if (-not $dockerRunning) {
    Write-LogWarning "Docker Desktop is not running - attempting to start it..."
    Write-Host ""

    # Try to find and start Docker Desktop
    $dockerDesktopPath = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"

    if (Test-Path $dockerDesktopPath) {
        Write-Log "Starting Docker Desktop..."
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Minimized

        # Wait for Docker to start - check every 5 seconds for up to 2 minutes
        $maxWaitSeconds = 120
        $waitInterval = 5
        $waited = 0

        Write-Log "Waiting for Docker to initialize - this may take up to 2 minutes..."
        Write-Host ""

        while ($waited -lt $maxWaitSeconds) {
            Start-Sleep -Seconds $waitInterval
            $waited += $waitInterval

            # Show progress
            $progress = [math]::Round(($waited / $maxWaitSeconds) * 100)
            Write-Host "`r  Waiting... $waited seconds / $maxWaitSeconds seconds - ${progress} percent complete" -NoNewline

            # Check if Docker is now running
            try {
                $dockerInfo = docker info 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $dockerRunning = $true
                    Write-Host ""
                    Write-Host ""
                    Write-LogSuccess "Docker Desktop started successfully!"
                    break
                }
            } catch { }
        }

        Write-Host ""

        if (-not $dockerRunning) {
            Write-Host ""
            Write-LogError "Docker Desktop failed to start within $maxWaitSeconds seconds"
            Write-Host ""
            Write-Log "Please try the following:"
            Write-Log "1. Open Docker Desktop manually from the Start Menu"
            Write-Log "2. Wait for it to fully start - look for whale icon in system tray"
            Write-Log "3. Run 'First-Time Setup' from the Start Menu"
            Wait-ForUserInput "Press Enter to exit..."
            exit 1
        }
    } else {
        Write-LogError "Could not find Docker Desktop executable"
        Write-Log "Please start Docker Desktop manually from the Start Menu"
        Write-Log "Then run 'First-Time Setup' from the Start Menu"
        Wait-ForUserInput "Press Enter to exit..."
        exit 1
    }
} else {
    Write-LogSuccess "Docker is already running!"
}

# Show Docker version
$dockerVersion = docker --version 2>&1
Write-Log "Docker version: $dockerVersion"

###############################################################################
# STEP 3: System Detection
###############################################################################
Write-LogStep "STEP 3/7: Detecting System Hardware"

try {
    $gpus = Get-WmiObject Win32_VideoController
    $hasGPU = $false
    foreach ($gpu in $gpus) {
        if ($gpu.Name -like "*NVIDIA*" -or $gpu.Name -like "*AMD*" -or $gpu.Name -like "*Radeon*") {
            $hasGPU = $true
            Write-Log "GPU detected: $($gpu.Name)"
        }
    }
    if (-not $hasGPU) {
        Write-Log "No dedicated GPU detected - will use CPU mode"
    }

    $ram = Get-WmiObject Win32_ComputerSystem
    $totalRAM = [math]::Round($ram.TotalPhysicalMemory / 1GB)
    Write-Log "System RAM: ${totalRAM}GB"
} catch {
    Write-LogWarning "Could not detect system specifications"
}

Write-LogSuccess "System detection complete"

###############################################################################
# STEP 4: Ollama Setup (Optional)
###############################################################################
Write-LogStep "STEP 4/7: Ollama Setup (Optional)"

$ollamaInstalled = Get-Command ollama -ErrorAction SilentlyContinue

if (-not $ollamaInstalled) {
    Write-LogWarning "Ollama is not installed"
    Write-Log "Ollama provides local LLM support for privacy and cost savings"
    Write-Host ""
    Write-Host "Would you like to install Ollama now? (Y/n): " -ForegroundColor Yellow -NoNewline
    $installOllama = Read-Host

    if ($installOllama -ne "n" -and $installOllama -ne "N") {
        Write-Log "Opening Ollama download page..."
        Start-Process "https://ollama.com/download/windows"
        Write-Host ""
        Write-Log "Please install Ollama from the browser window that just opened." -Color Yellow
        Write-Log "After installation completes, press Enter to continue..." -Color Yellow
        Write-Host ""
        Read-Host "Press Enter after Ollama is installed"

        # Check if Ollama is now installed
        $ollamaInstalled = Get-Command ollama -ErrorAction SilentlyContinue
        if ($ollamaInstalled) {
            Write-LogSuccess "Ollama installation detected!"
        } else {
            Write-LogWarning "Ollama not detected yet - it may require a system restart"
            Write-Log "After restarting, use Start Menu, then GenAI Research, then Download Models"
        }
    }
}

# Ollama model download instructions (manual process)
if ($ollamaInstalled) {
    Write-LogSuccess "Ollama is installed"
    Write-Host ""
    Write-Log "To download AI models, open a NEW PowerShell or Command Prompt window and run:"
    Write-Host ""
    Write-Host "  RECOMMENDED MODELS (Text):" -ForegroundColor Yellow
    Write-Host "    ollama pull llama3.2:3b" -ForegroundColor Cyan
    Write-Host "    ollama pull llama3.1:8b" -ForegroundColor Cyan
    Write-Host "    ollama pull phi3:mini" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  EMBEDDING MODELS (Required for RAG):" -ForegroundColor Yellow
    Write-Host "    ollama pull snowflake-arctic-embed2" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  VISION MODELS (for document/image analysis):" -ForegroundColor Yellow
    Write-Host "    ollama pull granite3.2-vision:2b" -ForegroundColor Cyan
    Write-Host "    ollama pull llava:7b" -ForegroundColor Cyan
    Write-Host "    ollama pull llava:13b" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Or run the auto-pull script after installation:" -ForegroundColor Yellow
    Write-Host "    .\scripts\pull-ollama-models.ps1 auto" -ForegroundColor Cyan
    Write-Host ""
    Write-Log "You can download these models now in another window, or after installation completes."
    Write-Log "The application will work with any models you have downloaded."
} else {
    Write-Log "Ollama not detected - you can install it later from: https://ollama.com/download/windows"
}

Write-LogSuccess "Step 4/7 Complete"

###############################################################################
# STEP 5: Build Docker Images
###############################################################################
Write-LogStep "STEP 5/7: Building Docker Images"

Set-Location $InstallDir

Write-Host ""
Write-Log "This is the longest step - typically 10-20 minutes" -Color Yellow
Write-Log "You will see Docker build output below..." -Color Yellow
Write-Host ""
Write-Host "────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# Build base-poetry-deps
Write-Host ""
Write-Log ">>> Building base-poetry-deps..." -Color Cyan
Write-Host ""

$baseBuildStart = Get-Date
docker compose build base-poetry-deps 2>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -Path $LogFile -Value $_ -ErrorAction SilentlyContinue
}
$baseExitCode = $LASTEXITCODE
$baseBuildDuration = [math]::Round(((Get-Date) - $baseBuildStart).TotalMinutes, 1)

Write-Host ""
if ($baseExitCode -eq 0) {
    Write-LogSuccess "base-poetry-deps built successfully! Duration: ${baseBuildDuration} minutes"
} else {
    Write-LogError "base-poetry-deps build FAILED - exit code: $baseExitCode"
    Write-Host ""
    if ($LogFile) { Write-Log "Check the log file for details: $LogFile" }
    Wait-ForUserInput "Press Enter to exit..."
    exit 1
}

# Build all application services
Write-Host ""
Write-Log ">>> Building application services..." -Color Cyan
Write-Host ""

$appBuildStart = Get-Date
docker compose build 2>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -Path $LogFile -Value $_ -ErrorAction SilentlyContinue
}
$appExitCode = $LASTEXITCODE
$appBuildDuration = [math]::Round(((Get-Date) - $appBuildStart).TotalMinutes, 1)

Write-Host ""
if ($appExitCode -eq 0) {
    Write-LogSuccess "Application services built successfully! Duration: ${appBuildDuration} minutes"
} else {
    Write-LogError "Application build FAILED - exit code: $appExitCode"
    Write-Host ""
    if ($LogFile) { Write-Log "Check the log file for details: $LogFile" }
    Wait-ForUserInput "Press Enter to exit..."
    exit 1
}

Write-Host "────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# Verify images were built
Write-Host ""
Write-Log "Verifying Docker images..."

$images = docker images --format "{{.Repository}}:{{.Tag}}" 2>&1
Write-Log "Built images:"
$images | ForEach-Object { Write-Log "  - $_" }

###############################################################################
# STEP 6: Start Services
###############################################################################
Write-LogStep "STEP 6/7: Starting Application Services"

Write-Log "Starting Docker containers..."

docker compose up -d 2>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -Path $LogFile -Value $_ -ErrorAction SilentlyContinue
}
$upExitCode = $LASTEXITCODE

if ($upExitCode -ne 0) {
    Write-LogError "Failed to start containers - exit code: $upExitCode"
    Wait-ForUserInput "Press Enter to exit..."
    exit 1
}

Write-Log "Waiting 20 seconds for services to initialize..."
Start-Sleep -Seconds 20

# Verify containers are running
Write-Log "Checking container status..."

$running = docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>&1
Write-Host ""
Write-Log "Container Status:"
$running | ForEach-Object { Write-Log "  $_" }

$runningCount = (docker compose ps --status running --format "{{.Name}}" 2>&1 | Measure-Object -Line).Lines

###############################################################################
# STEP 7: Verify Services
###############################################################################
Write-LogStep "STEP 7/7: Verifying Services"

if ($runningCount -gt 0) {
    Write-LogSuccess "$runningCount containers running"
} else {
    Write-LogWarning "No containers appear to be running"
    Write-Log "You may need to start services manually using the Start Menu shortcut"
}

###############################################################################
# INSTALLATION COMPLETE
###############################################################################
$totalDuration = [math]::Round(((Get-Date) - $StartTime).TotalMinutes, 1)

Write-Host ""
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                                  ║" -ForegroundColor Green
Write-Host "║              INSTALLATION COMPLETED SUCCESSFULLY!                ║" -ForegroundColor Green
Write-Host "║                                                                  ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-LogSuccess "Total installation time: $totalDuration minutes"
Write-LogSuccess "Containers running: $runningCount"
Write-Host ""
Write-Log "Application URLs:" -Color Cyan
Write-Log "  • Streamlit UI:  http://localhost:8501" -Color White
Write-Log "  • FastAPI:       http://localhost:9020" -Color White
Write-Log "  • ChromaDB:      http://localhost:8001" -Color White
Write-Host ""
Write-Log "Use Start Menu shortcuts to manage the application."
if ($LogFile) {
    Write-Log "Log file saved to: $LogFile"
}
Write-Host ""

# ALWAYS wait for user input before closing
Wait-ForUserInput "Press Enter to close this window..."

exit 0
