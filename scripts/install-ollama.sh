#!/bin/bash
###############################################################################
# Ollama Installation Script
# Installs Ollama for local model support
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "         Ollama Installation for Local Model Support"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if already installed
if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
    print_warning "Ollama is already installed (version: $OLLAMA_VERSION)"
    read -p "Reinstall? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installation cancelled"
        exit 0
    fi
fi

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Linux*)
        print_info "Installing Ollama for Linux..."
        curl -fsSL https://ollama.com/install.sh | sh
        ;;
    Darwin*)
        print_info "Installing Ollama for macOS..."
        print_warning "Please download and install Ollama from: https://ollama.com/download/mac"
        print_info "Or use Homebrew: brew install ollama"
        exit 0
        ;;
    *)
        print_error "Unsupported operating system: $OS"
        exit 1
        ;;
esac

# Configure Ollama to listen on all interfaces (for Docker access)
print_info "Configuring Ollama for Docker access..."
sudo mkdir -p /etc/systemd/system/ollama.service.d/
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

# Reload systemd and enable service for future boots
sudo systemctl daemon-reload
sudo systemctl enable ollama

print_success "Ollama installed successfully!"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Next Steps (REQUIRED)"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "You must manually start Ollama and pull models:"
echo ""
echo "  1. Start Ollama server:"
echo "     ollama serve &"
echo ""
echo "  2. In a new terminal (or wait for server to start), pull models:"
echo ""
echo "     # Pull recommended text models for chat/generation (~9 GB)"
echo "     /opt/jitc_genai/scripts/pull-ollama-models.sh recommended"
echo ""
echo "     # Pull vision models for image understanding (~14.5 GB)"
echo "     # Includes: granite3.2-vision:2b, llava:7b, llava:13b"
echo "     /opt/jitc_genai/scripts/pull-ollama-models.sh vision"
echo ""
echo "  3. Test a model:"
echo "     ollama run llama3.1:8b"
echo ""
echo "For auto-start on boot, the systemd service is enabled."
echo "After a reboot, Ollama should start automatically."
echo ""
