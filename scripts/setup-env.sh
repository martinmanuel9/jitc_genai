#!/bin/bash
###############################################################################
# Environment Setup Script
# Simple configuration wizard - only prompts for API keys
# All other settings use pre-configured defaults from .env.template
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

INSTALL_DIR="${INSTALL_DIR:-/opt/jitc_genai}"
ENV_FILE="$INSTALL_DIR/.env"
ENV_TEMPLATE="$INSTALL_DIR/.env.template"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "         GenAI Research - Environment Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Create .env from template if it doesn't exist, or update existing
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_TEMPLATE" ]; then
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        print_success "Created .env from template with default settings"
    else
        print_error "Template file not found: $ENV_TEMPLATE"
        exit 1
    fi
else
    print_info "Using existing .env file"
fi

echo ""
print_header "=== API Keys Configuration ==="
echo ""
print_info "All other settings are pre-configured with working defaults."
echo ""

# OpenAI API Key
print_info "OpenAI API Key (required for cloud models like GPT-4, GPT-4o)"
read -p "Enter OpenAI API Key (press Enter to skip): " OPENAI_KEY
if [ -n "$OPENAI_KEY" ]; then
    sed -i "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" "$ENV_FILE"
    print_success "OpenAI API key configured"
else
    print_warning "OpenAI API key not configured"
    print_info "You can use local Ollama models instead, or add the key later to .env"
fi

echo ""

# LangSmith (Optional)
print_info "LangSmith API Key (optional - for debugging and monitoring)"
read -p "Enter LangSmith API Key (press Enter to skip): " LANGSMITH_KEY
if [ -n "$LANGSMITH_KEY" ]; then
    read -p "Enter LangSmith project name: " LANGSMITH_PROJECT
    sed -i "s/^LANGCHAIN_API_KEY=.*/LANGCHAIN_API_KEY=$LANGSMITH_KEY/" "$ENV_FILE"
    sed -i "s/^LANGSMITH_PROJECT=.*/LANGSMITH_PROJECT=$LANGSMITH_PROJECT/" "$ENV_FILE"
    sed -i "s/^LANGSMITH_TRACING=.*/LANGSMITH_TRACING=true/" "$ENV_FILE"
    print_success "LangSmith tracing enabled"
else
    print_info "LangSmith tracing disabled (can be enabled later in .env)"
fi

echo ""
print_header "=== Ollama (Local LLM Support) ==="
echo ""

if command -v ollama &> /dev/null; then
    print_success "Ollama is installed"
else
    print_warning "Ollama is NOT installed"
    echo ""
    echo "To install Ollama for local model support, run:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
fi

echo ""
echo "After installing Ollama, you must manually start the server and pull models:"
echo ""
echo "  1. Start Ollama server:"
echo "     OLLAMA_HOST=0.0.0.0:11434 ollama serve &"
echo ""
echo "  2. Pull models (in a new terminal or after server starts):"
echo ""
echo "     # Pull recommended text models for chat/generation (~9 GB)"
echo "     $INSTALL_DIR/scripts/pull-ollama-models.sh recommended"
echo ""
echo "     # Pull vision models for image understanding (~14.5 GB)"
echo "     # Includes: granite3.2-vision:2b, llava:7b, llava:13b"
echo "     $INSTALL_DIR/scripts/pull-ollama-models.sh vision"
echo ""
print_info "See $INSTALL_DIR/INSTALL.md for detailed instructions."

echo ""
print_header "=== Setup Complete ==="
echo ""

print_success "Environment configuration completed!"
echo ""
echo "Configuration file: $ENV_FILE"
echo ""
print_info "Pre-configured services (ready to use):"
echo "  - FastAPI Backend: http://localhost:9020"
echo "  - Streamlit Web UI: http://localhost:8501"
echo "  - PostgreSQL: localhost:5432"
echo "  - ChromaDB: localhost:8001"
echo "  - Redis: localhost:6379"
if command -v ollama &> /dev/null; then
    echo "  - Ollama: http://localhost:11434"
fi

echo ""
print_info "To start the application:"
echo "  sudo systemctl start jitc_genai"
echo ""
print_info "Or manually with Docker Compose:"
echo "  cd $INSTALL_DIR && docker compose up -d"
echo ""
