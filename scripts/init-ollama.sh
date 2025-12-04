#!/bin/bash
# Ollama Model Initialization Script
# This script pulls required models after Ollama starts

set -e

echo "=== Ollama Model Initialization ==="
echo "Waiting for Ollama to be ready..."

# Wait for Ollama to be available
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://ollama:11434/api/tags > /dev/null 2>&1; then
        echo "✓ Ollama is ready!"
        break
    fi
    echo "Waiting for Ollama... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Timeout waiting for Ollama to start"
    exit 1
fi

# Pull models
MODELS="${OLLAMA_MODELS:-llama3.2:latest}"

# Split models by comma (POSIX-compatible)
echo "$MODELS" | tr ',' '\n' | while read -r MODEL; do
    # Trim whitespace (POSIX-compatible)
    MODEL=$(echo "$MODEL" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    if [ -z "$MODEL" ]; then
        continue
    fi

    echo ""
    echo "=== Pulling model: $MODEL ==="

    # Check if model already exists
    if curl -s http://ollama:11434/api/tags | grep -q "\"name\":\"$MODEL\""; then
        echo "✓ Model $MODEL already exists, skipping..."
        continue
    fi

    echo "Pulling $MODEL (this may take several minutes)..."

    # Pull model using Ollama API with streaming disabled
    RESPONSE=$(curl -s -X POST http://ollama:11434/api/pull \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$MODEL\",\"stream\":false}")

    if echo "$RESPONSE" | grep -q "success"; then
        echo "✓ Successfully pulled $MODEL"
    else
        echo "⚠ Warning: Failed to pull $MODEL"
        echo "Response: $RESPONSE"
    fi
done

echo ""
echo "=== Model initialization complete ==="
echo "Available models:"
curl -s http://ollama:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || echo "Could not list models"
