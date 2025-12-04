#!/bin/bash
# Platform-agnostic GENAI Validation System setup

# Configuration
REPO_URL="https://github.com/martinmanuel9/litigation_genai.git"

# Get current directory
CURRENT_DIR="$(pwd)"
PROJECT_NAME="$(basename "$CURRENT_DIR")"
echo "Setting up AI project: $PROJECT_NAME"
echo "Current directory: $CURRENT_DIR"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Docker not found!"
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check Docker Compose
DOCKER_COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "Neither docker-compose nor docker compose found!"
    exit 1
fi
echo "Using compose command: $DOCKER_COMPOSE_CMD"

# Check for .env
if [ ! -f "$CURRENT_DIR/.env" ]; then
    echo ".env file not found in $CURRENT_DIR"
    echo "Please create it before continuing."
    exit 1
fi
echo "Found .env file"

# Skip repo clone if local source exists
if [ -f "$CURRENT_DIR/docker-compose.yml" ]; then
    echo "Project already present. Skipping git clone."
else
    echo "Cloning repository from $REPO_URL..."
    git clone "$REPO_URL" "$CURRENT_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to clone. Please check your Git setup or clone manually."
        exit 1
    fi
fi

# Create data/model/logs directories
echo "Creating necessary directories..."
mkdir -p "$CURRENT_DIR/data/chromadb"
mkdir -p "$CURRENT_DIR/data/postgres"
mkdir -p "$CURRENT_DIR/data/huggingface_cache"
mkdir -p "$CURRENT_DIR/models"
mkdir -p "$CURRENT_DIR/logs"

# Create .venv directory for local poetry management
echo "Creating .venv directory for local poetry management..."
if [ ! -d "$CURRENT_DIR/.venv" ]; then
    mkdir -p "$CURRENT_DIR/.venv"
    echo ".venv directory created successfully"
else
    echo ".venv directory already exists"
fi

# Setup Poetry for local development
echo "Setting up Poetry for local development..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Poetry not found. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    
    # Add Poetry to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"
    
    echo "Poetry installed. You may need to restart your terminal or run:"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
else
    echo "Poetry is already installed"
fi

# Configure Poetry to use the .venv directory
echo "Configuring Poetry to use local .venv directory..."
poetry config virtualenvs.in-project true
poetry config virtualenvs.path "$CURRENT_DIR/.venv"

# Install dependencies if pyproject.toml exists
if [ -f "$CURRENT_DIR/pyproject.toml" ]; then
    echo "Installing Poetry dependencies..."
    cd "$CURRENT_DIR"
    poetry install
    echo "Poetry dependencies installed successfully"
else
    echo "No pyproject.toml found. Skipping Poetry dependency installation."
fi

# Add enhanced start/stop scripts
cat > "$CURRENT_DIR/start.sh" <<EOL
#!/bin/bash
# AI system startup script

cd "\$(dirname "\$0")"

echo "Starting AI System..."
echo "Location: \$(pwd)"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found"
fi

# Start services
echo "Starting Docker services..."
$DOCKER_COMPOSE_CMD build base-poetry-deps
$DOCKER_COMPOSE_CMD up --build -d

echo ""
echo "Waiting for services to initialize..."
sleep 10

# Check service health
echo "Checking service status..."
if curl -s http://localhost:9020/health > /dev/null; then
    echo "FastAPI service: Running"
else
    echo "FastAPI service: Starting"
fi

if curl -s http://localhost:8501 > /dev/null; then
    echo "Streamlit service: Running"
else
    echo "Streamlit service: Starting"
fi

echo ""
echo "AI system startup complete!"
echo "Access points:"
echo "   Streamlit UI: http://localhost:8501"
echo "   FastAPI: http://localhost:9020"
echo "   ChromaDB: http://localhost:8020"
echo ""
echo "To check logs: docker-compose logs -f [service_name]"
echo "To stop system: ./scripts/stop.sh"
EOL

cat > "$CURRENT_DIR/stop.sh" <<EOL
#!/bin/bash
# Enhanced AI system shutdown script

cd "\$(dirname "\$0")"

echo "Stopping AI Validation System..."
$DOCKER_COMPOSE_CMD down

echo "Cleaning up..."
docker system prune -a 2>/dev/null || true

echo "AI system stopped and cleaned up."
echo "Data preserved in ./data/ directory"
echo "To restart: ./scripts/start.sh"
EOL

chmod +x "$CURRENT_DIR/start.sh" "$CURRENT_DIR/stop.sh"

echo ""
echo "AI Installation complete!"
echo ""
echo "Available commands:"
echo "   ./scripts/start.sh    - Start the AI system"
echo "   ./scripts/stop.sh     - Stop the AI system"
echo "   ./scripts/models.sh   - Manage AI models"
echo ""


read -p "Start AI system now? (y/n): " start_now
if [[ "$start_now" =~ ^[Yy]$ ]]; then
    "$CURRENT_DIR/start.sh"
fi