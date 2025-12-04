#!/bin/bash
###############################################################################
# Installation Verification Script
# Verifies that all components of GenAI Research are properly installed
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
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_header() { echo -e "${BLUE}=== $1 ===${NC}"; }

INSTALL_DIR="${INSTALL_DIR:-/opt/jitc_genai}"
ISSUES_FOUND=0

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  GenAI Research - Installation Verification"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check 1: Installation directory exists
print_header "Installation Directory"
if [ -d "$INSTALL_DIR" ]; then
    print_success "Installation directory exists: $INSTALL_DIR"
else
    print_error "Installation directory not found: $INSTALL_DIR"
    ((ISSUES_FOUND++))
fi

# Check 2: Source code files
print_header "Source Code Files"
REQUIRED_DIRS=("src" "scripts")
REQUIRED_FILES=("docker-compose.yml" ".env" "VERSION" "README.md")

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$INSTALL_DIR/$dir" ]; then
        print_success "Directory found: $dir"
        # Count files in directory
        file_count=$(find "$INSTALL_DIR/$dir" -type f | wc -l)
        echo "  └─ Contains $file_count files"
    else
        print_error "Directory missing: $dir"
        ((ISSUES_FOUND++))
    fi
done

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$INSTALL_DIR/$file" ]; then
        print_success "File found: $file"
    else
        print_error "File missing: $file"
        ((ISSUES_FOUND++))
    fi
done

# Check 3: Environment variables
print_header "Environment Configuration"
if [ -f "$INSTALL_DIR/.env" ]; then
    print_success ".env file exists"

    # Check if it's configured (not just template)
    if grep -q "^OPENAI_API_KEY=.*[a-zA-Z0-9]" "$INSTALL_DIR/.env" 2>/dev/null; then
        print_success "OpenAI API key configured"
    else
        print_warning "OpenAI API key not configured (cloud models won't work)"
    fi

    if grep -q "^DB_PASSWORD=.*[a-zA-Z0-9]" "$INSTALL_DIR/.env" 2>/dev/null; then
        print_success "Database password configured"
    else
        print_warning "Database password not configured"
    fi

    if grep -q "^DATABASE_URL=.*" "$INSTALL_DIR/.env" 2>/dev/null; then
        print_success "Database URL configured"
    else
        print_error "Database URL not configured"
        ((ISSUES_FOUND++))
    fi
else
    print_error ".env file not found"
    ((ISSUES_FOUND++))
fi

# Check 4: Docker installation
print_header "Docker Environment"
if command -v docker &> /dev/null; then
    docker_version=$(docker --version | awk '{print $3}' | tr -d ',')
    print_success "Docker installed: $docker_version"

    if docker info &> /dev/null; then
        print_success "Docker daemon running"
    else
        print_error "Docker daemon not running"
        ((ISSUES_FOUND++))
    fi
else
    print_error "Docker not installed"
    ((ISSUES_FOUND++))
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    compose_version=$(docker-compose --version | awk '{print $3}' | tr -d ',')
    print_success "Docker Compose installed: $compose_version"
elif docker compose version &> /dev/null; then
    compose_version=$(docker compose version --short)
    print_success "Docker Compose plugin installed: $compose_version"
else
    print_error "Docker Compose not installed"
    ((ISSUES_FOUND++))
fi

# Check 5: Ollama (optional)
print_header "Ollama (Optional - for local models)"
if command -v ollama &> /dev/null; then
    print_success "Ollama installed"

    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        print_success "Ollama service running"

        # Check installed models
        model_count=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
        if [ "$model_count" -gt 0 ]; then
            print_success "Ollama models installed: $model_count"
            echo ""
            echo "  Installed models:"
            ollama list 2>/dev/null | tail -n +2 | while read line; do
                model_name=$(echo "$line" | awk '{print $1}')
                echo "    - $model_name"
            done
        else
            print_warning "No Ollama models installed"
            echo "  Run: $INSTALL_DIR/scripts/pull-ollama-models.sh auto"
        fi
    else
        print_warning "Ollama service not running"
        echo "  Run: sudo systemctl start ollama"
    fi
else
    print_warning "Ollama not installed (local models not available)"
    echo "  Run: $INSTALL_DIR/scripts/install-ollama.sh"
fi

# Check 6: System service
print_header "Systemd Service"
if systemctl list-unit-files | grep -q "jitc_genai.service"; then
    print_success "Systemd service installed"

    if systemctl is-enabled --quiet jitc_genai 2>/dev/null; then
        print_success "Service enabled (auto-start on boot)"
    else
        print_warning "Service not enabled for auto-start"
        echo "  Run: sudo systemctl enable jitc_genai"
    fi

    if systemctl is-active --quiet jitc_genai 2>/dev/null; then
        print_success "Service running"
    else
        print_warning "Service not running"
        echo "  Run: sudo systemctl start jitc_genai"
    fi
else
    print_error "Systemd service not installed"
    ((ISSUES_FOUND++))
fi

# Check 7: Running containers (if service is active)
print_header "Docker Containers"
if systemctl is-active --quiet jitc_genai 2>/dev/null || docker ps --format "{{.Names}}" | grep -q "fastapi\|streamlit"; then
    expected_containers=("fastapi" "streamlit" "postgres" "chromadb" "redis" "celery-worker")
    running_count=0

    for container in "${expected_containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            print_success "Container running: $container"
            ((running_count++))
        else
            print_warning "Container not running: $container"
        fi
    done

    echo ""
    echo "  Running: $running_count / ${#expected_containers[@]} containers"
else
    print_warning "No containers running (service not started)"
fi

# Check 8: Port accessibility
print_header "Network Accessibility"
ports=("8501:Streamlit UI" "9020:FastAPI" "8001:ChromaDB")

for port_info in "${ports[@]}"; do
    port=$(echo "$port_info" | cut -d':' -f1)
    service=$(echo "$port_info" | cut -d':' -f2)

    if nc -z localhost "$port" 2>/dev/null || curl -s "http://localhost:$port" &> /dev/null; then
        print_success "$service accessible on port $port"
    else
        print_warning "$service not accessible on port $port"
    fi
done

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Verification Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ "$ISSUES_FOUND" -eq 0 ]; then
    print_success "Installation verification passed!"
    echo ""
    echo "Your GenAI Research installation appears to be complete."
    echo ""
    echo "Access the application at: http://localhost:8501"
else
    print_warning "Found $ISSUES_FOUND critical issues"
    echo ""
    echo "Please address the issues marked with [✗] above."
    echo ""
    echo "For help, see:"
    echo "  - Installation guide: $INSTALL_DIR/INSTALL.md"
    echo "  - README: $INSTALL_DIR/README.md"
    echo "  - GitHub issues: https://github.com/martinmanuel9/jitc_genai/issues"
fi

echo ""
exit $ISSUES_FOUND
