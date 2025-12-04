###############################################################################
# Docker Utilities Module for GenAI Research
# Shared functions used by all installer scripts
#
# Usage: . "$PSScriptRoot\docker-utils.ps1" [-ForMSI]
#
# The -ForMSI switch changes output format for MSI installer logging
###############################################################################

param(
    [switch]$ForMSI = $false,
    [string]$LogFilePath = ""
)

# Store MSI mode in script scope for use by functions
$script:IsMSIMode = $ForMSI
$script:LogFile = $LogFilePath

###############################################################################
# Logging Functions - Output differs based on MSI vs Interactive mode
###############################################################################
function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($script:IsMSIMode) {
        Write-Host "CustomAction: $Message"
        [System.Console]::Out.Flush()
    } else {
        Write-Host "[INFO] $Message" -ForegroundColor Cyan
    }

    # Write to log file if specified
    if ($script:LogFile) {
        Add-Content -Path $script:LogFile -Value "[$timestamp] [INFO] $Message" -ErrorAction SilentlyContinue
    }
}

function Write-LogSuccess {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($script:IsMSIMode) {
        Write-Host "CustomAction: SUCCESS: $Message"
        [System.Console]::Out.Flush()
    } else {
        Write-Host "[SUCCESS] $Message" -ForegroundColor Green
    }

    if ($script:LogFile) {
        Add-Content -Path $script:LogFile -Value "[$timestamp] [SUCCESS] $Message" -ErrorAction SilentlyContinue
    }
}

function Write-LogError {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($script:IsMSIMode) {
        Write-Host "CustomAction: ERROR: $Message"
        [System.Console]::Out.Flush()
    } else {
        Write-Host "[ERROR] $Message" -ForegroundColor Red
    }

    if ($script:LogFile) {
        Add-Content -Path $script:LogFile -Value "[$timestamp] [ERROR] $Message" -ErrorAction SilentlyContinue
    }
}

function Write-LogWarning {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($script:IsMSIMode) {
        Write-Host "CustomAction: WARNING: $Message"
        [System.Console]::Out.Flush()
    } else {
        Write-Host "[WARNING] $Message" -ForegroundColor Yellow
    }

    if ($script:LogFile) {
        Add-Content -Path $script:LogFile -Value "[$timestamp] [WARNING] $Message" -ErrorAction SilentlyContinue
    }
}

function Write-LogStep {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($script:IsMSIMode) {
        Write-Host ""
        Write-Host "CustomAction: =============================================="
        Write-Host "CustomAction: $Message"
        Write-Host "CustomAction: =============================================="
        Write-Host ""
        [System.Console]::Out.Flush()
    } else {
        Write-Host ""
        Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host "  $Message" -ForegroundColor Cyan
        Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
        Write-Host ""
    }

    if ($script:LogFile) {
        Add-Content -Path $script:LogFile -Value "" -ErrorAction SilentlyContinue
        Add-Content -Path $script:LogFile -Value "[$timestamp] =============================================" -ErrorAction SilentlyContinue
        Add-Content -Path $script:LogFile -Value "[$timestamp] $Message" -ErrorAction SilentlyContinue
        Add-Content -Path $script:LogFile -Value "[$timestamp] =============================================" -ErrorAction SilentlyContinue
    }
}

###############################################################################
# Docker Status Functions
###############################################################################
function Test-DockerRunning {
    try {
        $null = docker info 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-DockerImagesExist {
    try {
        $images = docker images --format "{{.Repository}}" 2>&1
        $hasBase = $images | Select-String -Pattern "base-poetry-deps" -Quiet
        $hasFastapi = $images | Select-String -Pattern "fastapi" -Quiet
        $hasStreamlit = $images | Select-String -Pattern "streamlit" -Quiet
        return ($hasBase -and $hasFastapi -and $hasStreamlit)
    } catch {
        return $false
    }
}

function Test-ContainersRunning {
    try {
        $running = docker compose ps --status running --format "{{.Name}}" 2>&1
        return ($LASTEXITCODE -eq 0 -and $running -and @($running).Count -gt 0)
    } catch {
        return $false
    }
}

###############################################################################
# Docker Build with Real-Time Streaming Output
# Returns: $true on success, $false on failure
###############################################################################
function Invoke-DockerBuild {
    param(
        [Parameter(Mandatory=$true)]
        [string]$WorkingDirectory,
        [string]$ServiceName = "",
        [int]$TimeoutMinutes = 25
    )

    $buildCommand = if ($ServiceName) { "docker compose build $ServiceName" } else { "docker compose build" }
    $displayName = if ($ServiceName) { $ServiceName } else { "all services" }

    Write-Log "Building: $displayName"
    Write-Log "Command: $buildCommand"
    Write-Log "Timeout: $TimeoutMinutes minutes"

    if ($script:IsMSIMode) {
        Write-Host "CustomAction: ----------------------------------------"
    } else {
        Write-Host "----------------------------------------" -ForegroundColor DarkGray
    }

    $startTime = Get-Date
    $timeoutMs = $TimeoutMinutes * 60 * 1000

    try {
        $pinfo = New-Object System.Diagnostics.ProcessStartInfo
        $pinfo.FileName = "cmd.exe"
        $pinfo.Arguments = "/c $buildCommand 2>&1"
        $pinfo.RedirectStandardOutput = $true
        $pinfo.RedirectStandardError = $true
        $pinfo.UseShellExecute = $false
        $pinfo.CreateNoWindow = $true
        $pinfo.WorkingDirectory = $WorkingDirectory

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $pinfo
        $process.Start() | Out-Null

        # Stream output in real-time
        while (-not $process.HasExited) {
            $line = $process.StandardOutput.ReadLine()
            if ($line) {
                if ($script:IsMSIMode) {
                    Write-Host "CustomAction: $line"
                    [System.Console]::Out.Flush()
                } else {
                    Write-Host $line
                }
            }

            # Check timeout
            $elapsed = (Get-Date) - $startTime
            if ($elapsed.TotalMilliseconds -gt $timeoutMs) {
                Write-LogError "Build timed out after $TimeoutMinutes minutes"
                $process.Kill()
                return $false
            }
        }

        # Read any remaining output
        $remaining = $process.StandardOutput.ReadToEnd()
        if ($remaining) {
            $remaining -split "`n" | ForEach-Object {
                if ($_.Trim()) {
                    if ($script:IsMSIMode) {
                        Write-Host "CustomAction: $_"
                    } else {
                        Write-Host $_
                    }
                }
            }
            if ($script:IsMSIMode) { [System.Console]::Out.Flush() }
        }

        $exitCode = $process.ExitCode
        $duration = (Get-Date) - $startTime

        if ($script:IsMSIMode) {
            Write-Host "CustomAction: ----------------------------------------"
        } else {
            Write-Host "----------------------------------------" -ForegroundColor DarkGray
        }
        Write-Log "Completed in $([math]::Round($duration.TotalMinutes, 1)) minutes"

        if ($exitCode -eq 0) {
            Write-LogSuccess "$displayName built successfully!"
            return $true
        } else {
            Write-LogError "Build failed with exit code: $exitCode"
            return $false
        }

    } catch {
        Write-LogError "Exception during build: $($_.Exception.Message)"
        return $false
    }
}

###############################################################################
# Verify Docker Images Were Built
# Returns: $true if all images exist, $false otherwise
###############################################################################
function Test-DockerImagesBuild {
    Write-Log "Verifying Docker images..."

    $requiredImages = @(
        @{ Name = "base-poetry-deps"; Pattern = "base-poetry-deps" },
        @{ Name = "FastAPI"; Pattern = "fastapi" },
        @{ Name = "Streamlit"; Pattern = "streamlit" }
    )

    $allFound = $true

    foreach ($img in $requiredImages) {
        $found = docker images --format "{{.Repository}}" 2>&1 | Select-String $img.Pattern
        if ($found) {
            Write-LogSuccess "Image verified: $($img.Name)"
        } else {
            Write-LogError "Image NOT found: $($img.Name)"
            $allFound = $false
        }
    }

    return $allFound
}

###############################################################################
# Start Docker Containers
# Returns: $true on success, $false on failure
###############################################################################
function Start-DockerContainers {
    param(
        [Parameter(Mandatory=$true)]
        [string]$WorkingDirectory,
        [int]$WaitSeconds = 20
    )

    Write-Log "Starting Docker containers..."

    Set-Location $WorkingDirectory

    $output = docker compose up -d 2>&1
    $exitCode = $LASTEXITCODE

    if ($output) {
        $output | ForEach-Object {
            if ($_ -and $_.ToString().Trim()) {
                Write-Log $_
            }
        }
    }

    if ($exitCode -ne 0) {
        Write-LogError "docker compose up failed with exit code: $exitCode"
        return $false
    }

    Write-Log "Waiting $WaitSeconds seconds for services to initialize..."
    Start-Sleep -Seconds $WaitSeconds

    # Verify containers are running
    if (Test-ContainersRunning) {
        $running = docker compose ps --status running --format "{{.Name}}" 2>&1
        Write-LogSuccess "Containers running:"
        $running | ForEach-Object { Write-LogSuccess "  - $_" }
        return $true
    } else {
        Write-LogError "No containers are running after startup!"
        return $false
    }
}

###############################################################################
# Full Build Workflow - Builds base, then all services, optionally starts
# Returns: $true on complete success, $false on any failure
###############################################################################
function Invoke-FullBuildWorkflow {
    param(
        [Parameter(Mandatory=$true)]
        [string]$InstallDir,
        [switch]$SkipIfImagesExist = $false,
        [switch]$StartContainers = $true
    )

    # Check Docker is running
    if (-not (Test-DockerRunning)) {
        Write-LogError "Docker Desktop is not running!"
        return $false
    }
    Write-LogSuccess "Docker is running"

    # Check if we should skip build
    if ($SkipIfImagesExist -and (Test-DockerImagesExist)) {
        Write-LogSuccess "Docker images already exist, skipping build"
    } else {
        # Build base-poetry-deps
        Write-LogStep "Building base-poetry-deps"

        if (-not (Invoke-DockerBuild -WorkingDirectory $InstallDir -ServiceName "base-poetry-deps" -TimeoutMinutes 25)) {
            Write-LogError "Failed to build base-poetry-deps"
            return $false
        }

        # Build all application services
        Write-LogStep "Building application services"

        if (-not (Invoke-DockerBuild -WorkingDirectory $InstallDir -TimeoutMinutes 20)) {
            Write-LogError "Failed to build application services"
            return $false
        }

        # Verify all images
        if (-not (Test-DockerImagesBuild)) {
            Write-LogError "Image verification failed"
            return $false
        }
    }

    # Start containers if requested
    if ($StartContainers) {
        Write-LogStep "Starting Application Services"

        if (-not (Start-DockerContainers -WorkingDirectory $InstallDir -WaitSeconds 20)) {
            Write-LogError "Failed to start containers"
            return $false
        }
    }

    Write-LogSuccess "Build workflow completed successfully!"
    return $true
}

###############################################################################
# System Detection - Returns recommended model based on hardware
###############################################################################
function Get-RecommendedModel {
    $hasGPU = $false
    $totalRAM = 8

    try {
        $gpus = Get-WmiObject Win32_VideoController
        foreach ($gpu in $gpus) {
            if ($gpu.Name -like "*NVIDIA*" -or $gpu.Name -like "*AMD*" -or $gpu.Name -like "*Radeon*") {
                $hasGPU = $true
                Write-Log "GPU detected: $($gpu.Name)"
            }
        }

        if (-not $hasGPU) {
            Write-Log "No dedicated GPU detected (CPU mode)"
        }

        $ram = Get-WmiObject Win32_ComputerSystem
        $totalRAM = [math]::Round($ram.TotalPhysicalMemory / 1GB)
        Write-Log "System RAM: ${totalRAM}GB"
    } catch {
        Write-LogWarning "Could not detect system specifications"
    }

    if ($hasGPU -and $totalRAM -ge 16) {
        return "llama3.1:8b"
    } elseif ($hasGPU) {
        return "llama3.2:3b"
    } else {
        return "llama3.2:1b"
    }
}
