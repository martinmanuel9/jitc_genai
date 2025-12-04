###############################################################################
# Ollama Model Auto-Pull Script for Windows
#
# This script automatically pulls recommended US-based Ollama models for
# the verification GenAI application.
#
# All models are from US-based organizations:
# - Meta (California)
# - Microsoft (Washington)
# - Snowflake (Montana)
# - IBM (New York) - Granite models
#
# Usage:
#   .\scripts\pull-ollama-models.ps1 [auto|quick|recommended|full|embeddings|vision]
#
# Options:
#   auto         - Auto-detect GPU and pull appropriate models [DEFAULT]
#   quick        - Pull only the fastest models (6.6 GB total)
#   recommended  - Pull production-ready models (9 GB total)
#   full         - Pull all available models including 70B variants (100+ GB)
#   embeddings   - Pull only embedding models for RAG
#   vision       - Pull vision/multimodal models for image understanding
###############################################################################

param(
    [Parameter(Position=0)]
    [ValidateSet("auto", "quick", "recommended", "full", "embeddings", "vision")]
    [string]$Mode = "auto"
)

$ErrorActionPreference = "Continue"

#region Helper Functions

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-WarningMsg {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-OllamaRunning {
    Write-Info "Checking if Ollama is running..."

    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg "Ollama is not installed. Please install it first."
        Write-Host "Visit: https://ollama.com/download/windows"
        return $false
    }

    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5 -ErrorAction Stop
        Write-Success "Ollama is running"
        return $true
    } catch {
        Write-ErrorMsg "Ollama service is not running or not accessible."
        Write-Host "Please start Ollama and try again."
        return $false
    }
}

function Invoke-PullModel {
    param(
        [string]$Model,
        [string]$Description
    )

    Write-Info "Pulling $Model - $Description"

    try {
        $process = Start-Process -FilePath "ollama" -ArgumentList "pull", $Model -NoNewWindow -Wait -PassThru
        if ($process.ExitCode -eq 0) {
            Write-Success "✓ $Model downloaded successfully"
            return $true
        } else {
            Write-ErrorMsg "✗ Failed to pull $Model"
            return $false
        }
    } catch {
        Write-ErrorMsg "✗ Failed to pull $Model : $_"
        return $false
    }
}

function Show-InstalledModels {
    Write-Info "Currently installed models:"
    ollama list
    Write-Host ""
}

function Get-GpuInfo {
    $gpuType = "none"
    $vramGb = 0
    $gpuName = ""

    # Check for NVIDIA GPU
    try {
        $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
        if ($nvidiaSmi) {
            $gpuType = "nvidia"
            $gpuName = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1).Trim()
            $vramMib = (nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null | Select-Object -First 1).Trim()

            if ($vramMib -and $vramMib -ne "[N/A]" -and $vramMib -ne "N/A") {
                $vramGb = [math]::Floor([int]$vramMib / 1024)
            }
        }
    } catch {
        # nvidia-smi not available
    }

    # Check for AMD GPU (basic detection on Windows)
    if ($gpuType -eq "none") {
        try {
            $amdGpu = Get-WmiObject Win32_VideoController | Where-Object { $_.Name -match "AMD|Radeon" }
            if ($amdGpu) {
                $gpuType = "amd"
                $gpuName = $amdGpu.Name
                # AMD VRAM detection on Windows is unreliable, default to 0
                $vramGb = 0
            }
        } catch {
            # WMI query failed
        }
    }

    return @{
        Type = $gpuType
        VramGb = $vramGb
        Name = $gpuName
    }
}

function Get-RecommendedTier {
    $gpu = Get-GpuInfo

    Write-Host ""
    Write-Info "Hardware Detection Results:"
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

    if ($gpu.Type -eq "none") {
        Write-WarningMsg "No GPU detected - CPU-only mode"
        Write-Host "  Recommended: Lightweight models optimized for CPU inference"
        Write-Host "  Models: llama3.2:1b, llama3.2:3b, phi3:mini, granite3.2-vision:2b"
        Write-Host "  Total Size: ~9.1 GB"
        Write-Host ""
        return 1  # CPU-only tier
    }

    if ($gpu.Type -eq "nvidia") {
        if ($gpu.VramGb -eq 0) {
            Write-WarningMsg "NVIDIA GPU detected: $($gpu.Name) (VRAM info unavailable)"
            Write-Host "  Note: Cannot determine exact VRAM, defaulting to balanced configuration"
        } else {
            Write-Success "NVIDIA GPU detected: $($gpu.Name)"
            Write-Host "  VRAM Available: $($gpu.VramGb) GB"
        }
    } elseif ($gpu.Type -eq "amd") {
        if ($gpu.VramGb -eq 0) {
            Write-WarningMsg "AMD GPU detected: $($gpu.Name) (VRAM info unavailable)"
            Write-Host "  Note: Cannot determine exact VRAM, defaulting to balanced configuration"
        } else {
            Write-Success "AMD GPU detected: $($gpu.Name)"
            Write-Host "  VRAM Available: $($gpu.VramGb) GB"
        }
    }

    Write-Host ""

    # Determine tier based on VRAM
    if ($gpu.VramGb -eq 0) {
        Write-Info "VRAM information unavailable - Recommending balanced models"
        Write-Host "  Models: llama3.2:3b, llama3.1:8b, phi3:mini, snowflake-arctic-embed2, granite3.2-vision:2b"
        Write-Host "  Total Size: ~14.2 GB"
        Write-Host ""
        Write-Host "  Tip: You can override this by running:" -ForegroundColor Yellow
        Write-Host "     .\scripts\pull-ollama-models.ps1 quick       # For lightweight models"
        Write-Host "     .\scripts\pull-ollama-models.ps1 recommended # For production models"
        Write-Host "     .\scripts\pull-ollama-models.ps1 vision      # For vision models only"
        Write-Host ""
        return 2  # Balanced tier
    } elseif ($gpu.VramGb -lt 8) {
        Write-WarningMsg "Limited VRAM (< 8 GB) - Recommending lightweight models"
        Write-Host "  Models: llama3.2:3b, phi3:mini, snowflake-arctic-embed2, granite3.2-vision:2b"
        Write-Host "  Total Size: ~9.5 GB"
        Write-Host ""
        return 1  # Lightweight tier
    } elseif ($gpu.VramGb -lt 16) {
        Write-Success "Moderate VRAM (8-16 GB) - Recommending balanced models"
        Write-Host "  Models: llama3.2:3b, llama3.1:8b, phi3:mini, snowflake-arctic-embed2, granite3.2-vision:2b, llava:7b"
        Write-Host "  Total Size: ~18.7 GB"
        Write-Host ""
        return 2  # Balanced tier
    } elseif ($gpu.VramGb -lt 40) {
        Write-Success "High VRAM (16-40 GB) - Recommending powerful models"
        Write-Host "  Models: llama3.1:8b, llama3:8b, phi3:medium, snowflake-arctic-embed2, llava:7b, llava:13b"
        Write-Host "  Total Size: ~31.8 GB"
        Write-Host ""
        return 3  # Powerful tier
    } else {
        Write-Success "Enterprise VRAM (40+ GB) - Can run largest models"
        Write-Host "  Models: All models including 70B variants and all vision models"
        Write-Host "  Note: 70B models are optional due to size (40 GB each)"
        Write-Host ""
        return 4  # Enterprise tier
    }
}

function Invoke-AutoPull {
    $tier = Get-RecommendedTier

    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host ""

    switch ($tier) {
        1 {
            # CPU-only or Low VRAM
            Write-Info "Pulling LIGHTWEIGHT models optimized for CPU/Low VRAM"
            Write-Host ""
            Invoke-PullModel "llama3.2:1b" "Meta's smallest - CPU optimized (1.3 GB)"
            Invoke-PullModel "llama3.2:3b" "Meta's balanced small model (2 GB)"
            Invoke-PullModel "phi3:mini" "Microsoft's efficient model (2.3 GB)"
            Invoke-PullModel "snowflake-arctic-embed2" "Snowflake embeddings v2 (1.7 GB)"
            # Vision model for low VRAM
            Invoke-PullModel "granite3.2-vision:2b" "IBM Granite Vision - lightweight multimodal (1.5 GB)"
        }
        2 {
            # 8-16 GB VRAM
            Write-Info "Pulling BALANCED models for moderate GPU (8-16 GB VRAM)"
            Write-Host ""
            Invoke-PullModel "llama3.2:3b" "Meta's balanced small model (2 GB)"
            Invoke-PullModel "llama3.1:8b" "Meta's powerful 8B model (4.7 GB)"
            Invoke-PullModel "phi3:mini" "Microsoft's efficient model (2.3 GB)"
            Invoke-PullModel "snowflake-arctic-embed2" "Snowflake embeddings v2 (1.7 GB)"
            # Vision models for moderate VRAM
            Invoke-PullModel "granite3.2-vision:2b" "IBM Granite Vision - lightweight multimodal (1.5 GB)"
            Invoke-PullModel "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
        }
        3 {
            # 16-40 GB VRAM
            Write-Info "Pulling POWERFUL models for high-end GPU (16-40 GB VRAM)"
            Write-Host ""
            Invoke-PullModel "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
            Invoke-PullModel "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
            Invoke-PullModel "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
            Invoke-PullModel "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"
            Invoke-PullModel "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
            # Vision models for high VRAM
            Invoke-PullModel "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
            Invoke-PullModel "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
        }
        4 {
            # 40+ GB VRAM
            Write-Info "Pulling ENTERPRISE models for high-end GPU (40+ GB VRAM)"
            Write-Host ""
            Write-WarningMsg "You have enough VRAM for 70B models (40 GB each)"
            $include70B = Read-Host "Include 70B models? (y/N)"

            if ($include70B -eq "y" -or $include70B -eq "Y") {
                # Full enterprise set with 70B
                Invoke-PullModel "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
                Invoke-PullModel "llama3.1:70b" "Meta Llama 3.1 70B (40 GB)"
                Invoke-PullModel "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
                Invoke-PullModel "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
                Invoke-PullModel "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"
                Invoke-PullModel "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
            } else {
                # Enterprise set without 70B
                Invoke-PullModel "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
                Invoke-PullModel "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
                Invoke-PullModel "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
                Invoke-PullModel "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"
                Invoke-PullModel "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
            }
            # All vision models for enterprise
            Invoke-PullModel "granite3.2-vision:2b" "IBM Granite Vision - lightweight multimodal (1.5 GB)"
            Invoke-PullModel "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
            Invoke-PullModel "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
        }
    }
}

#endregion

#region Main Script

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "         Ollama Model Auto-Pull Script" -ForegroundColor Green
Write-Host "         US-Based Models Only - On-Premises Deployment" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Check Ollama
if (-not (Test-OllamaRunning)) {
    exit 1
}

Write-Host ""
Write-Info "Mode: $Mode"
Write-Host ""

switch ($Mode) {
    "auto" {
        Write-Info "AUTO mode - Detecting GPU and selecting optimal models"
        Invoke-AutoPull
    }

    "quick" {
        Write-Info "Pulling QUICK models (fastest inference, ~6.6 GB total)"
        Write-Host ""

        Invoke-PullModel "llama3.2:1b" "Meta's smallest (1.3 GB)"
        Invoke-PullModel "llama3.2:3b" "Meta's balanced (2 GB)"
        Invoke-PullModel "phi3:mini" "Microsoft's efficient (2.3 GB)"
        Invoke-PullModel "snowflake-arctic-embed" "Snowflake embeddings (1 GB)"
    }

    "recommended" {
        Write-Info "Pulling RECOMMENDED text models (production-ready, ~9 GB total)"
        Write-Host ""

        Invoke-PullModel "llama3.2:3b" "Meta's balanced model (2 GB)"
        Invoke-PullModel "llama3.1:8b" "Meta's powerful 8B (4.7 GB)"
        Invoke-PullModel "phi3:mini" "Microsoft's efficient model (2.3 GB)"
    }

    "full" {
        Write-WarningMsg "Pulling ALL models including 70B variants (100+ GB total)"
        Write-WarningMsg "This will take a long time and requires ~120 GB disk space"
        $continue = Read-Host "Continue? (y/N)"

        if ($continue -ne "y" -and $continue -ne "Y") {
            Write-Info "Cancelled"
            exit 0
        }
        Write-Host ""

        # Llama 3.2 Series
        Invoke-PullModel "llama3.2:1b" "Meta Llama 3.2 1B (1.3 GB)"
        Invoke-PullModel "llama3.2:3b" "Meta Llama 3.2 3B (2 GB)"

        # Llama 3.1 Series
        Invoke-PullModel "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
        Invoke-PullModel "llama3.1:70b" "Meta Llama 3.1 70B (40 GB) - LARGE!"

        # Llama 3 Series
        Invoke-PullModel "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
        Invoke-PullModel "llama3:70b" "Meta Llama 3 70B (40 GB) - LARGE!"

        # Microsoft Phi Series
        Invoke-PullModel "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
        Invoke-PullModel "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"

        # Snowflake Embeddings
        Invoke-PullModel "snowflake-arctic-embed" "Snowflake Arctic Embed (1 GB)"
        Invoke-PullModel "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"

        # Vision/Multimodal Models
        Invoke-PullModel "granite3.2-vision:2b" "IBM Granite Vision 2B (1.5 GB)"
        Invoke-PullModel "llava:7b" "LLaVA 1.6 7B - vision-language (4.7 GB)"
        Invoke-PullModel "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
    }

    "embeddings" {
        Write-Info "Pulling EMBEDDING models (for RAG and semantic search)"
        Write-Host ""

        Invoke-PullModel "snowflake-arctic-embed" "Snowflake Arctic Embed (1 GB)"
        Invoke-PullModel "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
    }

    "vision" {
        Write-Info "Pulling VISION/MULTIMODAL models (for image understanding)"
        Write-Host ""

        Invoke-PullModel "granite3.2-vision:2b" "IBM Granite Vision 2B - lightweight (1.5 GB)"
        Invoke-PullModel "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
        Invoke-PullModel "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
    }
}

Write-Host ""
Write-Success "Model pull complete!"
Write-Host ""

# Show installed models
Show-InstalledModels

# Summary
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "         Summary" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Info "To use these models in your application:"
Write-Host "  1. Ensure Ollama is configured to listen on 0.0.0.0:11434"
Write-Host "  2. Models are now available in FastAPI and Streamlit"
Write-Host "  3. Select models from dropdown menus or API calls"
Write-Host ""
Write-Info "To test a model:"
Write-Host "  ollama run llama3.1:8b"
Write-Host ""
Write-Success "All done! Your models are ready to use."
Write-Host ""

#endregion
