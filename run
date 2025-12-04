#!/bin/bash
# Convenience launcher for scripts in ./scripts/ directory
# Usage: ./run <script-name> [args...]
# Example: ./run start
#          ./run backup --volumes-only

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_PATH="$SCRIPT_DIR/scripts"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

show_help() {
    echo "Litigation GenAI Script Launcher"
    echo ""
    echo "Usage: ./run <command> [arguments...]"
    echo ""
    echo "Available commands:"
    echo ""
    echo "  System Control:"
    echo "    start                - Start the AI system"
    echo "    stop                 - Stop the AI system"
    echo "    restart              - Restart services"
    echo ""
    echo "  Data Management:"
    echo "    backup [options]     - Backup system data"
    echo "    restore <dir>        - Restore from backup"
    echo ""
    echo "  Setup & Configuration:"
    echo "    installer            - Run installation wizard"
    echo "    validation           - Validate system configuration"
    echo "    switch-env           - Switch between environments"
    echo ""
    echo "  AI Models:"
    echo "    models [command]     - Manage Ollama models"
    echo ""
    echo "  Testing & Deployment:"
    echo "    test-deployment      - Run deployment tests"
    echo ""
    echo "Examples:"
    echo "  ./run start"
    echo "  ./run backup --volumes-only"
    echo "  ./run restore backups/20241102_120000"
    echo "  ./run models list"
    echo ""
    echo "For script-specific help:"
    echo "  ./run <command> --help"
    echo ""
}

if [ $# -eq 0 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
fi

COMMAND="$1"
shift  # Remove command from arguments

# Map friendly names to script filenames
case "$COMMAND" in
    start)
        SCRIPT="start.sh"
        ;;
    stop)
        SCRIPT="stop.sh"
        ;;
    restart)
        SCRIPT="restart-services.sh"
        ;;
    backup)
        SCRIPT="backup.sh"
        ;;
    restore)
        SCRIPT="restore.sh"
        ;;
    installer|install)
        SCRIPT="installer.sh"
        ;;
    validation|validate)
        SCRIPT="validation.sh"
        ;;
    switch-env|env)
        SCRIPT="switch-env.sh"
        ;;
    models|model)
        SCRIPT="models.sh"
        ;;
    test-deployment|test)
        SCRIPT="test-deployment.sh"
        ;;
    init-ollama)
        SCRIPT="init-ollama.sh"
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$COMMAND'${NC}"
        echo ""
        echo "Run './run --help' to see available commands"
        exit 1
        ;;
esac

SCRIPT_PATH="$SCRIPTS_PATH/$SCRIPT"

if [ ! -f "$SCRIPT_PATH" ]; then
    echo -e "${RED}Error: Script not found: $SCRIPT_PATH${NC}"
    exit 1
fi

if [ ! -x "$SCRIPT_PATH" ]; then
    echo -e "${YELLOW}Making script executable: $SCRIPT${NC}"
    chmod +x "$SCRIPT_PATH"
fi

# Execute the script with remaining arguments
echo -e "${GREEN}Running: $SCRIPT${NC}"
echo ""
exec "$SCRIPT_PATH" "$@"
