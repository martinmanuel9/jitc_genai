#!/bin/bash
# Data backup script for litigation_genai project
# Backs up PostgreSQL, ChromaDB, Redis, and application data

set -e  # Exit on error

# Change to project root (parent of scripts directory)
cd "$(dirname "$0")/.."

# Configuration
BACKUP_ROOT="./backups"
BACKUP_DIR="$BACKUP_ROOT/$(date +%Y%m%d_%H%M%S)"
DB_ONLY=false
INCLUDE_HF_CACHE=false
VOLUMES_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --db-only)
            DB_ONLY=true
            shift
            ;;
        --volumes-only)
            VOLUMES_ONLY=true
            shift
            ;;
        --include-models)
            INCLUDE_HF_CACHE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Backup Modes:"
            echo "  (default)          Full backup: all volumes + application data"
            echo "  --volumes-only     Only Docker volumes (Postgres, ChromaDB, Redis)"
            echo "  --db-only          Alias for --volumes-only (deprecated)"
            echo ""
            echo "Options:"
            echo "  --include-models   Also backup HuggingFace model cache (large)"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "Docker Volumes Backed Up:"
            echo "  • genai_postgres_data  (PostgreSQL database)"
            echo "  • genai_chroma_data    (ChromaDB vectors)"
            echo "  • genai_redis_data     (Redis cache)"
            echo "  • genai_hf_cache       (with --include-models)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Handle legacy flag
if [ "$DB_ONLY" = true ]; then
    VOLUMES_ONLY=true
fi

mkdir -p "$BACKUP_DIR"

echo "========================================="
echo "Litigation GenAI - Data Backup"
echo "========================================="
echo "Backup location: $BACKUP_DIR"
echo "Mode: $(if [ "$VOLUMES_ONLY" = true ]; then echo "Docker Volumes Only"; else echo "Full (Volumes + App Data)"; fi)"
echo "Include HF models: $(if [ "$INCLUDE_HF_CACHE" = true ]; then echo "Yes"; else echo "No"; fi)"
echo ""

# Function to check if container is running
check_container() {
    local container=$1
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "ERROR: Container '$container' is not running!"
        echo "Please start your services with: docker compose up -d"
        exit 1
    fi
}

# Check all required containers are running
echo "[1/7] Checking Docker containers..."
check_container "postgres_db"
check_container "chromadb"
check_container "redis"
echo "✓ All containers are running"
echo ""

# Backup PostgreSQL database
echo "[2/7] Backing up PostgreSQL volume..."
if docker exec postgres_db pg_dumpall -U g3nA1-user > "$BACKUP_DIR/postgres_backup.sql" 2>/dev/null; then
    POSTGRES_SIZE=$(du -h "$BACKUP_DIR/postgres_backup.sql" | cut -f1)
    echo "✓ PostgreSQL backup complete ($POSTGRES_SIZE)"
else
    echo "✗ PostgreSQL backup failed!"
    exit 1
fi
echo ""

# Backup ChromaDB data (FIXED PATH: /chroma/chroma as per docker-compose.yml)
echo "[3/7] Backing up ChromaDB volume..."
if docker cp chromadb:/chroma/chroma "$BACKUP_DIR/chromadb_data" 2>/dev/null; then
    CHROMA_SIZE=$(du -sh "$BACKUP_DIR/chromadb_data" | cut -f1)
    echo "✓ ChromaDB backup complete ($CHROMA_SIZE)"
else
    echo "✗ ChromaDB backup failed!"
    exit 1
fi
echo ""

# Backup Redis data
echo "[4/7] Backing up Redis volume..."
docker exec redis redis-cli BGSAVE > /dev/null 2>&1 || echo "Warning: Redis BGSAVE failed, attempting direct copy..."
sleep 2  # Reduced from 5 seconds
if docker cp redis:/data "$BACKUP_DIR/redis_data" 2>/dev/null; then
    REDIS_SIZE=$(du -sh "$BACKUP_DIR/redis_data" | cut -f1)
    echo "✓ Redis backup complete ($REDIS_SIZE)"
else
    echo "✗ Redis backup failed!"
    exit 1
fi
echo ""

# Backup HuggingFace cache (optional, can be large)
echo "[5/7] Backing up HuggingFace model cache..."
if [ "$INCLUDE_HF_CACHE" = true ]; then
    if docker volume inspect genai_hf_cache > /dev/null 2>&1; then
        HF_BACKUP="$BACKUP_DIR/huggingface_cache"

        # Copy from volume using temporary container
        docker run --rm \
            -v genai_hf_cache:/source \
            -v "$PWD/$HF_BACKUP":/backup \
            alpine sh -c "cp -r /source/. /backup/" 2>/dev/null

        if [ $? -eq 0 ]; then
            HF_SIZE=$(du -sh "$HF_BACKUP" | cut -f1)
            echo "✓ HuggingFace cache backup complete ($HF_SIZE)"
        else
            echo "⚠ HuggingFace cache backup failed (non-critical)"
        fi
    else
        echo "⊘ HuggingFace cache volume not found"
    fi
else
    echo "⊘ Skipped (use --include-models to backup)"
fi
echo ""

# Backup application data (only if not volumes-only mode)
if [ "$VOLUMES_ONLY" = false ]; then
    echo "[6/7] Backing up application data..."

    # Backup uploaded images
    if [ -d "./stored_images" ]; then
        cp -r ./stored_images "$BACKUP_DIR/stored_images"
        echo "  ✓ Stored images backed up"
    fi

    # Backup local data directories
    if [ -d "./data" ]; then
        cp -r ./data "$BACKUP_DIR/local_data"
        echo "  ✓ Local data backed up"
    fi

    # Backup migrations (important for database schema)
    if [ -d "./migrations" ]; then
        cp -r ./migrations "$BACKUP_DIR/migrations"
        echo "  ✓ Migrations backed up"
    fi

    echo "✓ Application data backup complete"
else
    echo "[6/7] Skipping application data (volumes-only mode)"
fi
echo ""

# Create backup metadata
echo "[7/7] Creating backup metadata..."
cat > "$BACKUP_DIR/backup_info.txt" <<EOL
Litigation GenAI - Backup Information
=====================================
Backup Date: $(date)
Backup Type: $(if [ "$VOLUMES_ONLY" = true ]; then echo "Docker Volumes Only"; else echo "Full Backup"; fi)
HF Models Included: $(if [ "$INCLUDE_HF_CACHE" = true ]; then echo "Yes"; else echo "No"; fi)
Hostname: $(hostname)
User: $(whoami)

Docker Volumes Backed Up:
-------------------------
✓ genai_postgres_data  (PostgreSQL)
✓ genai_chroma_data    (ChromaDB)
✓ genai_redis_data     (Redis)
$(if [ "$INCLUDE_HF_CACHE" = true ]; then echo "✓ genai_hf_cache       (HuggingFace)"; else echo "✗ genai_hf_cache       (not included)"; fi)

Docker Containers Status:
------------------------
$(docker ps --filter "name=postgres_db|chromadb|redis" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}")

Git Information:
----------------
Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")
Commit: $(git rev-parse --short HEAD 2>/dev/null || echo "N/A")
Status: $(git status --short 2>/dev/null | wc -l) modified files

Backup Contents & Sizes:
-----------------------
PostgreSQL:  $(du -h "$BACKUP_DIR/postgres_backup.sql" 2>/dev/null | cut -f1 || echo "N/A")
ChromaDB:    $(du -sh "$BACKUP_DIR/chromadb_data" 2>/dev/null | cut -f1 || echo "N/A")
Redis:       $(du -sh "$BACKUP_DIR/redis_data" 2>/dev/null | cut -f1 || echo "N/A")
$(if [ "$INCLUDE_HF_CACHE" = true ] && [ -d "$BACKUP_DIR/huggingface_cache" ]; then echo "HF Cache:    $(du -sh "$BACKUP_DIR/huggingface_cache" | cut -f1)"; fi)
Total Size:  $(du -sh "$BACKUP_DIR" | cut -f1)
EOL
echo "✓ Metadata created"
echo ""

# Summary
echo "========================================="
echo "✅ BACKUP COMPLETED SUCCESSFULLY!"
echo "========================================="
echo "📁 Location: $BACKUP_DIR"
echo "💾 Size: $(du -sh "$BACKUP_DIR" | cut -f1)"
echo ""
echo "To restore this backup, run:"
echo "  ./restore.sh $BACKUP_DIR"
echo ""
echo "To list all backups:"
echo "  ls -lh $BACKUP_ROOT/"
echo "========================================="