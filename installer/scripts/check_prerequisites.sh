#!/bin/bash
###############################################################################
# Prerequisites Check Script
# Validates system requirements before installation
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

ERRORS=0
WARNINGS=0

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "         GenAI Research - Prerequisites Check"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Function to compare versions
version_ge() {
    [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

# Check OS
print_info "Checking operating system..."
OS="$(uname -s)"
case "$OS" in
    Linux*)     OS_TYPE="Linux";;
    Darwin*)    OS_TYPE="macOS";;
    *)          OS_TYPE="Unknown";;
esac
print_success "Operating System: $OS_TYPE"

# Check CPU cores
print_info "Checking CPU cores..."
if [ "$OS_TYPE" = "macOS" ]; then
    CPU_CORES=$(sysctl -n hw.ncpu)
else
    CPU_CORES=$(nproc)
fi

if [ "$CPU_CORES" -ge 4 ]; then
    print_success "CPU Cores: $CPU_CORES (minimum: 4)"
else
    print_warning "CPU Cores: $CPU_CORES (recommended: 4+)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check RAM
print_info "Checking available RAM..."
if [ "$OS_TYPE" = "macOS" ]; then
    RAM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
else
    RAM_GB=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 / 1024 ))
fi

if [ "$RAM_GB" -ge 8 ]; then
    print_success "RAM: ${RAM_GB} GB (minimum: 8 GB)"
else
    print_error "RAM: ${RAM_GB} GB (minimum required: 8 GB)"
    ERRORS=$((ERRORS + 1))
fi

# Check disk space
print_info "Checking available disk space..."
if [ "$OS_TYPE" = "macOS" ]; then
    DISK_AVAIL_GB=$(df -g / | tail -1 | awk '{print $4}')
else
    DISK_AVAIL_GB=$(df -BG / | tail -1 | awk '{print $4}' | sed 's/G//')
fi

if [ "$DISK_AVAIL_GB" -ge 50 ]; then
    print_success "Disk Space: ${DISK_AVAIL_GB} GB available (minimum: 50 GB)"
else
    print_error "Disk Space: ${DISK_AVAIL_GB} GB available (minimum required: 50 GB)"
    ERRORS=$((ERRORS + 1))
fi

# Check Docker
print_info "Checking Docker installation..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if version_ge "$DOCKER_VERSION" "24.0.0"; then
        print_success "Docker: $DOCKER_VERSION (minimum: 24.0.0)"

        # Check if Docker daemon is running
        if docker info &> /dev/null; then
            print_success "Docker daemon is running"
        else
            print_error "Docker is installed but daemon is not running"
            print_info "  Try: sudo systemctl start docker"
            ERRORS=$((ERRORS + 1))
        fi
    else
        print_error "Docker: $DOCKER_VERSION (minimum required: 24.0.0)"
        ERRORS=$((ERRORS + 1))
    fi
else
    print_error "Docker is not installed"
    print_info "  Install from: https://docs.docker.com/get-docker/"
    ERRORS=$((ERRORS + 1))
fi

# Check Docker Compose
print_info "Checking Docker Compose installation..."
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if version_ge "$COMPOSE_VERSION" "2.20.0"; then
        print_success "Docker Compose: $COMPOSE_VERSION (minimum: 2.20.0)"
    else
        print_error "Docker Compose: $COMPOSE_VERSION (minimum required: 2.20.0)"
        ERRORS=$((ERRORS + 1))
    fi
else
    print_error "Docker Compose (V2) is not installed"
    print_info "  Install from: https://docs.docker.com/compose/install/"
    ERRORS=$((ERRORS + 1))
fi

# Check required ports are available
print_info "Checking if required ports are available..."
REQUIRED_PORTS=(5432 6379 8001 8501 9020)
PORT_CONFLICTS=0

for port in "${REQUIRED_PORTS[@]}"; do
    if [ "$OS_TYPE" = "macOS" ]; then
        if lsof -Pi :$port -sTCP:LISTEN -t &> /dev/null; then
            print_warning "Port $port is already in use"
            PORT_CONFLICTS=$((PORT_CONFLICTS + 1))
        fi
    else
        if ss -ltn | grep -q ":$port "; then
            print_warning "Port $port is already in use"
            PORT_CONFLICTS=$((PORT_CONFLICTS + 1))
        fi
    fi
done

if [ "$PORT_CONFLICTS" -eq 0 ]; then
    print_success "All required ports are available (5432, 6379, 8001, 8501, 9020)"
else
    print_warning "$PORT_CONFLICTS required port(s) in use - installation may require port configuration"
    WARNINGS=$((WARNINGS + 1))
fi

# Check optional: Ollama
print_info "Checking optional components..."
if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
    print_success "Ollama: $OLLAMA_VERSION (optional - for local models)"

    if systemctl is-active --quiet ollama 2>/dev/null || pgrep -x ollama &> /dev/null; then
        print_success "Ollama service is running"
    else
        print_info "  Ollama is installed but not running"
        print_info "  Start with: sudo systemctl start ollama"
    fi
else
    print_info "Ollama: Not installed (optional - install for local model support)"
    print_info "  Install from: https://ollama.com/download"
fi

# Check optional: NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1)
    print_success "NVIDIA GPU detected: $GPU_NAME (optional - for accelerated inference)"
else
    print_info "No NVIDIA GPU detected (optional - CPU inference will be used)"
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "                      Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    print_success "All prerequisites are met! Ready to install."
    echo ""
    exit 0
elif [ "$ERRORS" -eq 0 ]; then
    print_warning "$WARNINGS warning(s) found - installation can proceed with caution"
    echo ""
    exit 0
else
    print_error "$ERRORS critical error(s) found - installation cannot proceed"
    echo ""
    echo "Please fix the errors above and run this check again."
    exit 1
fi
