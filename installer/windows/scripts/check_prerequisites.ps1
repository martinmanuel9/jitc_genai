# Windows Prerequisites Check Script
# Validates system requirements before installation

param(
    [switch]$Silent = $false
)

$ErrorActionPreference = "Stop"
$script:Errors = 0
$script:Warnings = 0

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[✓] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
    $script:Warnings++
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[✗] $Message" -ForegroundColor Red
    $script:Errors++
}

function Compare-Version {
    param(
        [string]$Version1,
        [string]$Version2
    )
    $v1 = [version]$Version1
    $v2 = [version]$Version2
    return $v1 -ge $v2
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host "         GenAI Research - Prerequisites Check"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

# Check Windows version
Write-Info "Checking Windows version..."
$os = Get-WmiObject -Class Win32_OperatingSystem
$osVersion = [System.Environment]::OSVersion.Version
if ($osVersion.Major -ge 10) {
    Write-Success "Windows Version: $($os.Caption) (Build $($osVersion.Build))"
} else {
    Write-ErrorMsg "Windows 10 or later is required"
}

# Check CPU cores
Write-Info "Checking CPU cores..."
$cpuCores = (Get-WmiObject -Class Win32_Processor).NumberOfLogicalProcessors
if ($cpuCores -ge 4) {
    Write-Success "CPU Cores: $cpuCores (minimum: 4)"
} else {
    Write-Warning "CPU Cores: $cpuCores (recommended: 4+)"
}

# Check RAM
Write-Info "Checking available RAM..."
$ram = [math]::Round((Get-WmiObject -Class Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
if ($ram -ge 8) {
    Write-Success "RAM: $ram GB (minimum: 8 GB)"
} else {
    Write-ErrorMsg "RAM: $ram GB (minimum required: 8 GB)"
}

# Check disk space
Write-Info "Checking available disk space..."
$disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'"
$freeSpaceGB = [math]::Round($disk.FreeSpace / 1GB, 2)
if ($freeSpaceGB -ge 50) {
    Write-Success "Disk Space: $freeSpaceGB GB available (minimum: 50 GB)"
} else {
    Write-ErrorMsg "Disk Space: $freeSpaceGB GB available (minimum required: 50 GB)"
}

# Check Docker Desktop
Write-Info "Checking Docker Desktop installation..."
$dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dockerPath) {
    try {
        $dockerVersion = & docker --version 2>&1
        if ($dockerVersion -match '(\d+\.\d+\.\d+)') {
            $version = $matches[1]
            if (Compare-Version $version "24.0.0") {
                Write-Success "Docker Desktop: $version (minimum: 24.0.0)"

                # Check if Docker daemon is running
                try {
                    $dockerInfo = & docker info 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "Docker daemon is running"
                    } else {
                        Write-ErrorMsg "Docker Desktop is installed but not running"
                        Write-Info "  Please start Docker Desktop from the Start menu"
                    }
                } catch {
                    Write-ErrorMsg "Cannot connect to Docker daemon"
                }
            } else {
                Write-ErrorMsg "Docker Desktop: $version (minimum required: 24.0.0)"
            }
        }
    } catch {
        Write-ErrorMsg "Docker command not available in PATH"
    }
} else {
    Write-ErrorMsg "Docker Desktop is not installed"
    Write-Info "  Download from: https://www.docker.com/products/docker-desktop"
}

# Check Docker Compose
Write-Info "Checking Docker Compose..."
try {
    $composeVersion = & docker compose version 2>&1
    if ($composeVersion -match '(\d+\.\d+\.\d+)') {
        $version = $matches[1]
        if (Compare-Version $version "2.20.0") {
            Write-Success "Docker Compose: $version (minimum: 2.20.0)"
        } else {
            Write-ErrorMsg "Docker Compose: $version (minimum required: 2.20.0)"
        }
    }
} catch {
    Write-ErrorMsg "Docker Compose (V2) is not available"
    Write-Info "  Update Docker Desktop to get Docker Compose V2"
}

# Check WSL 2 (required for Docker Desktop)
Write-Info "Checking WSL 2..."
try {
    $wslVersion = & wsl --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "WSL 2 is installed"
    } else {
        Write-Warning "WSL 2 may not be installed - required for Docker Desktop"
        Write-Info "  Install with: wsl --install"
    }
} catch {
    Write-Warning "Cannot verify WSL 2 installation"
}

# Check required ports
Write-Info "Checking if required ports are available..."
$requiredPorts = @(5432, 6379, 8000, 8501, 9020)
$portConflicts = 0

foreach ($port in $requiredPorts) {
    $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connection) {
        Write-Warning "Port $port is already in use"
        $portConflicts++
    }
}

if ($portConflicts -eq 0) {
    Write-Success "All required ports are available (5432, 6379, 8000, 8501, 9020)"
} else {
    Write-Warning "$portConflicts required port(s) in use - installation may require port configuration"
}

# Check optional: NVIDIA GPU
Write-Info "Checking optional components..."
try {
    $gpu = Get-WmiObject -Class Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" }
    if ($gpu) {
        Write-Success "NVIDIA GPU detected: $($gpu.Name) (optional - for accelerated inference)"
    } else {
        Write-Info "No NVIDIA GPU detected (optional - CPU inference will be used)"
    }
} catch {
    Write-Info "Cannot detect GPU information"
}

# Summary
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host "                      Summary"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

if ($script:Errors -eq 0 -and $script:Warnings -eq 0) {
    Write-Success "All prerequisites are met! Ready to install."
    Write-Host ""
    exit 0
} elseif ($script:Errors -eq 0) {
    Write-Warning "$script:Warnings warning(s) found - installation can proceed with caution"
    Write-Host ""
    exit 0
} else {
    Write-ErrorMsg "$script:Errors critical error(s) found - installation cannot proceed"
    Write-Host ""
    Write-Host "Please fix the errors above and run this check again."
    exit 1
}
