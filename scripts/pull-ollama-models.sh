#!/bin/bash
###############################################################################
# Ollama Model Auto-Pull Script
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
#   ./scripts/pull-ollama-models.sh [auto|quick|recommended|full|embeddings|vision]
#
# Options:
#   auto         - Auto-detect GPU and pull appropriate models [DEFAULT]
#   quick        - Pull only the fastest models (6.6 GB total)
#   recommended  - Pull production-ready models (9 GB total)
#   full         - Pull all available models including 70B variants (90+ GB)
#   embeddings   - Pull only embedding models for RAG
#   vision       - Pull vision/multimodal models for image understanding
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Ollama is running
check_ollama() {
    print_info "Checking if Ollama is running..."
    if ! command -v ollama &> /dev/null; then
        print_error "Ollama is not installed. Please install it first."
        echo "Visit: https://ollama.com/download"
        exit 1
    fi

    if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
        print_error "Ollama service is not running or not accessible."
        echo "Try: sudo systemctl start ollama"
        exit 1
    fi

    print_success "Ollama is running"
}

# Function to pull a model with progress
pull_model() {
    local model=$1
    local description=$2

    print_info "Pulling $model - $description"

    if ollama pull "$model"; then
        print_success "✓ $model downloaded successfully"
        return 0
    else
        print_error "✗ Failed to pull $model"
        return 1
    fi
}

# Function to show current models
show_models() {
    print_info "Currently installed models:"
    ollama list
    echo ""
}

# Function to detect GPU capabilities
detect_gpu() {
    local gpu_type="none"
    local vram_gb=0
    local gpu_name=""

    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        gpu_type="nvidia"
        # Get GPU name
        gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1)

        # Get total VRAM in GB (convert from MiB)
        vram_mib=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1)

        # Handle virtual/cloud GPUs that don't report memory (returns [N/A] or empty)
        if [ "$vram_mib" = "[N/A]" ] || [ -z "$vram_mib" ] || [ "$vram_mib" = "N/A" ]; then
            # Virtual GPU detected - assume moderate capabilities
            vram_gb=0
        else
            vram_gb=$((vram_mib / 1024))
        fi
    # Check for AMD GPU
    elif command -v rocm-smi &> /dev/null; then
        gpu_type="amd"
        gpu_name=$(rocm-smi --showproductname 2>/dev/null | grep "GPU" | head -n1 || echo "AMD GPU")
        # Try to get VRAM from rocm-smi
        vram_mib=$(rocm-smi --showmeminfo vram 2>/dev/null | grep "Total Memory" | awk '{print $4}' || echo "0")
        vram_gb=$((vram_mib / 1024))
    fi

    echo "$gpu_type|$vram_gb|$gpu_name"
}

# Function to recommend models based on hardware
recommend_models() {
    local gpu_info=$(detect_gpu)
    local gpu_type=$(echo "$gpu_info" | cut -d'|' -f1)
    local vram_gb=$(echo "$gpu_info" | cut -d'|' -f2)
    local gpu_name=$(echo "$gpu_info" | cut -d'|' -f3)

    echo ""
    print_info "Hardware Detection Results:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ "$gpu_type" = "none" ]; then
        print_warning "No GPU detected - CPU-only mode"
        echo "  Recommended: Lightweight models optimized for CPU inference"
        echo "  Models: llama3.2:1b, llama3.2:3b, phi3:mini, granite3.2-vision:2b"
        echo "  Total Size: ~9.1 GB"
        echo ""
        return 1  # CPU-only tier
    elif [ "$gpu_type" = "nvidia" ]; then
        if [ "$vram_gb" -eq 0 ]; then
            print_warning "NVIDIA GPU detected: $gpu_name (Virtual/Cloud GPU - VRAM info unavailable)"
            echo "  Note: Cannot determine exact VRAM, defaulting to balanced configuration"
        else
            print_success "NVIDIA GPU detected: $gpu_name"
            echo "  VRAM Available: ${vram_gb} GB"
        fi
    elif [ "$gpu_type" = "amd" ]; then
        if [ "$vram_gb" -eq 0 ]; then
            print_warning "AMD GPU detected: $gpu_name (VRAM info unavailable)"
            echo "  Note: Cannot determine exact VRAM, defaulting to balanced configuration"
        else
            print_success "AMD GPU detected: $gpu_name"
            echo "  VRAM Available: ${vram_gb} GB"
        fi
    fi

    echo ""

    # Determine tier based on VRAM
    if [ "$vram_gb" -eq 0 ]; then
        # GPU detected but VRAM unknown (virtual GPU or detection failed)
        print_info "VRAM information unavailable - Recommending balanced models"
        echo "  Models: llama3.2:3b, llama3.1:8b, phi3:mini, snowflake-arctic-embed2, granite3.2-vision:2b"
        echo "  Total Size: ~14.2 GB"
        echo ""
        echo "  💡 Tip: You can override this by running:"
        echo "     ./scripts/pull-ollama-models.sh quick      # For lightweight models"
        echo "     ./scripts/pull-ollama-models.sh recommended # For production models"
        echo "     ./scripts/pull-ollama-models.sh vision      # For vision models only"
        echo ""
        return 2  # Balanced tier (safe default for unknown GPU)
    elif [ "$vram_gb" -lt 8 ]; then
        print_warning "Limited VRAM (< 8 GB) - Recommending lightweight models"
        echo "  Models: llama3.2:3b, phi3:mini, snowflake-arctic-embed2, granite3.2-vision:2b"
        echo "  Total Size: ~9.5 GB"
        echo ""
        return 1  # Lightweight tier
    elif [ "$vram_gb" -lt 16 ]; then
        print_success "Moderate VRAM (8-16 GB) - Recommending balanced models"
        echo "  Models: llama3.2:3b, llama3.1:8b, phi3:mini, snowflake-arctic-embed2, granite3.2-vision:2b, llava:7b"
        echo "  Total Size: ~18.7 GB"
        echo ""
        return 2  # Balanced tier
    elif [ "$vram_gb" -lt 40 ]; then
        print_success "High VRAM (16-40 GB) - Recommending powerful models"
        echo "  Models: llama3.1:8b, llama3:8b, phi3:medium, snowflake-arctic-embed2, llava:7b, llava:13b"
        echo "  Total Size: ~31.8 GB"
        echo ""
        return 3  # Powerful tier
    else
        print_success "Enterprise VRAM (40+ GB) - Can run largest models"
        echo "  Models: All models including 70B variants and all vision models"
        echo "  Note: 70B models are optional due to size (40 GB each)"
        echo ""
        return 4  # Enterprise tier
    fi
}

# Function to pull models for auto mode
pull_auto_models() {
    recommend_models
    local tier=$?

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    case $tier in
        1)  # CPU-only or Low VRAM
            print_info "Pulling LIGHTWEIGHT models optimized for CPU/Low VRAM"
            echo ""
            pull_model "llama3.2:1b" "Meta's smallest - CPU optimized (1.3 GB)"
            pull_model "llama3.2:3b" "Meta's balanced small model (2 GB)"
            pull_model "phi3:mini" "Microsoft's efficient model (2.3 GB)"
            pull_model "snowflake-arctic-embed2" "Snowflake embeddings v2 (1.7 GB)"
            # Vision model for low VRAM
            pull_model "granite3.2-vision:2b" "IBM Granite Vision - lightweight multimodal (1.5 GB)"
            ;;
        2)  # 8-16 GB VRAM
            print_info "Pulling BALANCED models for moderate GPU (8-16 GB VRAM)"
            echo ""
            pull_model "llama3.2:3b" "Meta's balanced small model (2 GB)"
            pull_model "llama3.1:8b" "Meta's powerful 8B model (4.7 GB)"
            pull_model "phi3:mini" "Microsoft's efficient model (2.3 GB)"
            pull_model "snowflake-arctic-embed2" "Snowflake embeddings v2 (1.7 GB)"
            # Vision models for moderate VRAM
            pull_model "granite3.2-vision:2b" "IBM Granite Vision - lightweight multimodal (1.5 GB)"
            pull_model "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
            ;;
        3)  # 16-40 GB VRAM
            print_info "Pulling POWERFUL models for high-end GPU (16-40 GB VRAM)"
            echo ""
            pull_model "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
            pull_model "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
            pull_model "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
            pull_model "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"
            pull_model "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
            # Vision models for high VRAM
            pull_model "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
            pull_model "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
            ;;
        4)  # 40+ GB VRAM
            print_info "Pulling ENTERPRISE models for high-end GPU (40+ GB VRAM)"
            echo ""
            print_warning "You have enough VRAM for 70B models (40 GB each)"
            read -p "Include 70B models? (y/N) " -n 1 -r
            echo ""

            if [[ $REPLY =~ ^[Yy]$ ]]; then
                # Full enterprise set with 70B
                pull_model "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
                pull_model "llama3.1:70b" "Meta Llama 3.1 70B (40 GB)"
                pull_model "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
                pull_model "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
                pull_model "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"
                pull_model "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
            else
                # Enterprise set without 70B
                pull_model "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
                pull_model "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
                pull_model "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
                pull_model "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"
                pull_model "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
            fi
            # All vision models for enterprise
            pull_model "granite3.2-vision:2b" "IBM Granite Vision - lightweight multimodal (1.5 GB)"
            pull_model "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
            pull_model "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
            ;;
    esac
}

# Parse command line argument
MODE=${1:-auto}

# Banner
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "         Ollama Model Auto-Pull Script"
echo "         US-Based Models Only - On-Premises Deployment"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check Ollama
check_ollama

echo ""
print_info "Mode: $MODE"
echo ""

# Model sets
case "$MODE" in
    auto)
        print_info "AUTO mode - Detecting GPU and selecting optimal models"
        pull_auto_models
        ;;

    quick)
        print_info "Pulling QUICK models (fastest inference, ~6.6 GB total)"
        echo ""

        pull_model "llama3.2:1b" "Meta's smallest (1.3 GB)"
        pull_model "llama3.2:3b" "Meta's balanced (2 GB)"
        pull_model "phi3:mini" "Microsoft's efficient (2.3 GB)"
        pull_model "snowflake-arctic-embed" "Snowflake embeddings (1 GB)"
        ;;

    recommended)
        print_info "Pulling RECOMMENDED text models (production-ready, ~9 GB total)"
        echo ""

        pull_model "llama3.2:3b" "Meta's balanced model (2 GB)"
        pull_model "llama3.1:8b" "Meta's powerful 8B (4.7 GB)"
        pull_model "phi3:mini" "Microsoft's efficient model (2.3 GB)"
        ;;

    full)
        print_warning "Pulling ALL models including 70B variants (100+ GB total)"
        print_warning "This will take a long time and requires ~120 GB disk space"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Cancelled"
            exit 0
        fi
        echo ""

        # Llama 3.2 Series
        pull_model "llama3.2:1b" "Meta Llama 3.2 1B (1.3 GB)"
        pull_model "llama3.2:3b" "Meta Llama 3.2 3B (2 GB)"

        # Llama 3.1 Series
        pull_model "llama3.1:8b" "Meta Llama 3.1 8B (4.7 GB)"
        pull_model "llama3.1:70b" "Meta Llama 3.1 70B (40 GB) - LARGE!"

        # Llama 3 Series
        pull_model "llama3:8b" "Meta Llama 3 8B (4.7 GB)"
        pull_model "llama3:70b" "Meta Llama 3 70B (40 GB) - LARGE!"

        # Microsoft Phi Series
        pull_model "phi3:mini" "Microsoft Phi-3 Mini (2.3 GB)"
        pull_model "phi3:medium" "Microsoft Phi-3 Medium (7.9 GB)"

        # Snowflake Embeddings
        pull_model "snowflake-arctic-embed" "Snowflake Arctic Embed (1 GB)"
        pull_model "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"

        # Vision/Multimodal Models
        pull_model "granite3.2-vision:2b" "IBM Granite Vision 2B (1.5 GB)"
        pull_model "llava:7b" "LLaVA 1.6 7B - vision-language (4.7 GB)"
        pull_model "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
        ;;

    embeddings)
        print_info "Pulling EMBEDDING models (for RAG and semantic search)"
        echo ""

        pull_model "snowflake-arctic-embed" "Snowflake Arctic Embed (1 GB)"
        pull_model "snowflake-arctic-embed2" "Snowflake Arctic Embed 2.0 (1.7 GB)"
        ;;

    vision)
        print_info "Pulling VISION/MULTIMODAL models (for image understanding)"
        echo ""

        pull_model "granite3.2-vision:2b" "IBM Granite Vision 2B - lightweight (1.5 GB)"
        pull_model "llava:7b" "LLaVA 1.6 7B - vision-language model (4.7 GB)"
        pull_model "llava:13b" "LLaVA 1.6 13B - larger multimodal (8 GB)"
        ;;

    *)
        print_error "Invalid mode: $MODE"
        echo ""
        echo "Usage: $0 [auto|quick|recommended|full|embeddings|vision]"
        echo ""
        echo "  auto         - Auto-detect GPU and pull appropriate models [DEFAULT]"
        echo "  quick        - Pull only the fastest models (6.6 GB total)"
        echo "  recommended  - Pull production-ready models (9 GB total)"
        echo "  full         - Pull all available models including 70B variants (100+ GB)"
        echo "  embeddings   - Pull only embedding models for RAG"
        echo "  vision       - Pull vision/multimodal models for image understanding"
        exit 1
        ;;
esac

echo ""
print_success "Model pull complete!"
echo ""

# Show installed models
show_models

# Summary
echo "═══════════════════════════════════════════════════════════════"
echo "         Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""
print_info "To use these models in your application:"
echo "  1. Ensure Ollama is configured to listen on 0.0.0.0:11434"
echo "  2. Models are now available in FastAPI and Streamlit"
echo "  3. Select models from dropdown menus or API calls"
echo ""
print_info "To test a model:"
echo "  ollama run llama3.1:8b"
echo ""
print_success "All done! Your models are ready to use."
echo ""
