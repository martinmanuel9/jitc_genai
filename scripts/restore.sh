#!/bin/bash
# Data restore script for litigation_genai project
# Restores PostgreSQL, ChromaDB, Redis, and application data from backup

set -e  # Exit on error (except where explicitly handled)

# Change to project root (parent of scripts directory)
cd "$(dirname "$0")/.."

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "========================================="
    echo "Litigation GenAI - Database Restore"
    echo "========================================="
    echo "Usage: ./scripts/restore.sh <backup_directory> [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --skip-confirmation  Skip confirmation prompt (for automation)"
    echo "  --help, -h           Show this help message"
    echo ""
    echo "Available backups:"
    echo "=========================================="
    if [ -d "./backups" ]; then
        ls -lh ./backups/ | tail -n +2 | awk '{printf "  %s %s %s  %-10s  %s\n", $6, $7, $8, $5, $9}'
    else
        echo "  No backups found in ./backups/"
    fi
    echo "========================================="
    exit 1
fi

BACKUP_DIR="$1"
SKIP_CONFIRM=false

# Parse additional arguments
shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-confirmation)
            SKIP_CONFIRM=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/restore.sh <backup_directory> [OPTIONS]"
            echo "Restore databases and application data from backup"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate backup directory
if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: Backup directory not found: $BACKUP_DIR"
    exit 1
fi

# Show backup info if available
echo "========================================="
echo "Litigation GenAI - Database Restore"
echo "========================================="
if [ -f "$BACKUP_DIR/backup_info.txt" ]; then
    echo ""
    cat "$BACKUP_DIR/backup_info.txt"
    echo ""
    echo "========================================="
fi

# Confirmation prompt
if [ "$SKIP_CONFIRM" = false ]; then
    echo ""
    echo "⚠️  WARNING: This will OVERWRITE existing data!"
    echo ""
    read -p "Continue with restore? (yes/N): " confirm

    if [[ ! "$confirm" =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Restore cancelled."
        exit 0
    fi
    echo ""
fi

# Function to check if backup file/dir exists
check_backup_item() {
    local item=$1
    local type=$2  # 'file' or 'directory'

    if [ "$type" = "file" ] && [ ! -f "$BACKUP_DIR/$item" ]; then
        return 1
    elif [ "$type" = "directory" ] && [ ! -d "$BACKUP_DIR/$item" ]; then
        return 1
    fi
    return 0
}

# Stop all services
echo "[1/7] Stopping Docker services..."
docker compose down
echo "✓ Services stopped"
echo ""

# Restore PostgreSQL database
echo "[2/7] Restoring PostgreSQL database..."
if check_backup_item "postgres_backup.sql" "file"; then
    docker compose up -d postgres
    echo "  Waiting for PostgreSQL to be ready..."
    sleep 5

    # Wait for PostgreSQL to accept connections
    for i in {1..30}; do
        if docker exec postgres_db pg_isready -U g3nA1-user > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Restore to the 'postgres' maintenance database since pg_dumpall creates all databases
    echo "  Running restore (this may take a minute)..."

    # Run restore and capture output
    RESTORE_OUTPUT=$(docker exec -i postgres_db psql -U g3nA1-user -d postgres < "$BACKUP_DIR/postgres_backup.sql" 2>&1)
    RESTORE_EXIT=$?

    # Check for real errors (ignore "already exists" warnings which are expected)
    REAL_ERRORS=$(echo "$RESTORE_OUTPUT" | grep -i "error" | grep -v "already exists" || true)

    if [ $RESTORE_EXIT -eq 0 ] || [ -z "$REAL_ERRORS" ]; then
        echo "✓ PostgreSQL restored successfully"
    else
        echo "✗ PostgreSQL restore failed with errors:"
        echo "$REAL_ERRORS"
        echo ""
        echo "Full output:"
        echo "$RESTORE_OUTPUT"
        exit 1
    fi
    docker compose down
else
    echo "⊘ No PostgreSQL backup found, skipping"
fi
echo ""

# Restore ChromaDB data (FIXED PATH: /chroma/chroma)
echo "[3/7] Restoring ChromaDB vector database..."
if check_backup_item "chromadb_data" "directory"; then
    # Convert to absolute path for docker run
    BACKUP_ABS_PATH="$(cd "$BACKUP_DIR" && pwd)/chromadb_data"

    docker volume rm genai_chroma_data 2>/dev/null || true
    docker volume create genai_chroma_data > /dev/null

    # FIXED: Use /chroma/chroma as destination (matching docker-compose.yml)
    if docker run --rm \
        -v genai_chroma_data:/chroma/chroma \
        -v "$BACKUP_ABS_PATH":/backup \
        alpine sh -c "cp -r /backup/. /chroma/chroma/" > /dev/null 2>&1; then
        echo "✓ ChromaDB restored successfully"
    else
        echo "✗ ChromaDB restore failed!"
        exit 1
    fi
else
    echo "⊘ No ChromaDB backup found, skipping"
fi
echo ""

# Restore Redis data
echo "[4/7] Restoring Redis cache..."
if check_backup_item "redis_data" "directory"; then
    BACKUP_ABS_PATH="$(cd "$BACKUP_DIR" && pwd)/redis_data"

    docker volume rm genai_redis_data 2>/dev/null || true
    docker volume create genai_redis_data > /dev/null

    if docker run --rm \
        -v genai_redis_data:/data \
        -v "$BACKUP_ABS_PATH":/backup \
        alpine sh -c "cp -r /backup/. /data/" > /dev/null 2>&1; then
        echo "✓ Redis restored successfully"
    else
        echo "✗ Redis restore failed!"
        exit 1
    fi
else
    echo "⊘ No Redis backup found, skipping"
fi
echo ""

# Restore application data
echo "[5/7] Restoring application data..."
RESTORED_COUNT=0

if check_backup_item "stored_images" "directory"; then
    rm -rf ./stored_images
    cp -r "$BACKUP_DIR/stored_images" ./stored_images
    echo "  ✓ Stored images restored"
    ((RESTORED_COUNT++))
fi

if check_backup_item "local_data" "directory"; then
    rm -rf ./data
    cp -r "$BACKUP_DIR/local_data" ./data
    echo "  ✓ Local data restored"
    ((RESTORED_COUNT++))
fi

if check_backup_item "migrations" "directory"; then
    rm -rf ./migrations
    cp -r "$BACKUP_DIR/migrations" ./migrations
    echo "  ✓ Migrations restored"
    ((RESTORED_COUNT++))
fi

if [ $RESTORED_COUNT -eq 0 ]; then
    echo "⊘ No application data found in backup"
else
    echo "✓ Restored $RESTORED_COUNT application data items"
fi
echo ""

# Note about source code (deprecated in new backup script)
echo "[6/7] Checking for legacy backup items..."
if check_backup_item "src" "directory"; then
    echo "⚠️  Found source code backup (legacy)"
    echo "   Source code restoration is skipped - use git to manage code"
fi
echo "✓ Legacy check complete"
echo ""

# Start all services
echo "[7/7] Starting Docker services..."
if docker compose up -d; then
    echo "✓ All services started"
    echo ""

    # Wait for services to be healthy
    echo "Waiting for services to be ready..."
    sleep 5

    # Check health
    echo ""
    echo "Service Status:"
    docker compose ps
else
    echo "✗ Failed to start services"
    exit 1
fi

# Summary
echo ""
echo "========================================="
echo "✅ RESTORE COMPLETED SUCCESSFULLY!"
echo "========================================="
echo "Restored from: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "  1. Verify services are running: docker compose ps"
echo "  2. Check logs if needed: docker compose logs -f"
echo "  3. Access the application as normal"
echo "========================================="