#!/bin/bash
# Check pipeline status directly from Redis (when FastAPI is busy)

COMMAND=$1
PIPELINE_ID=$2

# If first arg looks like a pipeline_id, treat as status check
if [[ "$COMMAND" == pipeline_* ]]; then
    PIPELINE_ID=$COMMAND
    COMMAND="status"
fi

# Function to list all pipelines
list_all_pipelines() {
    echo "==========================================="
    echo "All Active Pipelines"
    echo "==========================================="
    echo ""

    PIPELINE_KEYS=$(docker exec redis redis-cli KEYS "pipeline:*:meta" | sed 's/pipeline://g' | sed 's/:meta//g' | sort -r)

    if [ -z "$PIPELINE_KEYS" ]; then
        echo "No pipelines found."
        exit 0
    fi

    COUNT=0
    for PID in $PIPELINE_KEYS; do
        COUNT=$((COUNT + 1))

        # Get status and title
        STATUS=$(docker exec redis redis-cli HGET "pipeline:$PID:meta" status)
        TITLE=$(docker exec redis redis-cli HGET "pipeline:$PID:meta" doc_title)
        CREATED=$(docker exec redis redis-cli HGET "pipeline:$PID:meta" created_at)
        RESULT_EXISTS=$(docker exec redis redis-cli EXISTS "pipeline:$PID:result")

        # Status emoji
        case "$STATUS" in
            "completed") EMOJI="✅" ;;
            "processing") EMOJI="⏳" ;;
            "queued") EMOJI="📝" ;;
            "failed") EMOJI="❌" ;;
            "cancelling") EMOJI="🛑" ;;
            *) EMOJI="❓" ;;
        esac

        echo "$COUNT. $EMOJI Pipeline ID: $PID"
        echo "   Title: $TITLE"
        echo "   Status: $STATUS"
        echo "   Created: $CREATED"

        if [ "$RESULT_EXISTS" -eq "1" ]; then
            echo "   Result: ✅ Available for download"
        fi

        echo ""
    done

    echo "==========================================="
    echo "Total pipelines: $COUNT"
    echo ""
    echo "To check specific pipeline:"
    echo "  ./check_pipeline_status.sh <pipeline_id>"
    echo "==========================================="
}

# Cancel pipeline function
cancel_pipeline() {
    local PID=$1

    if [ -z "$PID" ]; then
        echo "Usage: ./check_pipeline_status.sh cancel <pipeline_id>"
        exit 1
    fi

    echo "==========================================="
    echo "Cancelling Pipeline"
    echo "==========================================="
    echo "Pipeline ID: $PID"
    echo ""

    # Check if pipeline exists
    EXISTS=$(docker exec redis redis-cli EXISTS "pipeline:$PID:meta")
    if [ "$EXISTS" -eq "0" ]; then
        echo "❌ Pipeline not found or expired"
        exit 1
    fi

    # Get current status
    STATUS=$(docker exec redis redis-cli HGET "pipeline:$PID:meta" status)

    if [ "$STATUS" != "queued" ] && [ "$STATUS" != "processing" ]; then
        echo "❌ Cannot cancel pipeline with status: $STATUS"
        echo "   Only 'queued' or 'processing' pipelines can be cancelled."
        exit 1
    fi

    # Set abort flag
    docker exec redis redis-cli SET "pipeline:$PID:abort" "1" EX 86400 > /dev/null

    # Update metadata
    docker exec redis redis-cli HSET "pipeline:$PID:meta" status "cancelling" > /dev/null
    docker exec redis redis-cli HSET "pipeline:$PID:meta" progress_message "Cancellation requested - stopping at next checkpoint..." > /dev/null

    echo "✅ Cancellation requested!"
    echo ""
    echo "The pipeline will:"
    echo "  • Stop at the next checkpoint"
    echo "  • Return partial results (sections completed so far)"
    echo "  • Update status to 'failed' or return aborted plan"
    echo ""
    echo "To check status:"
    echo "  ./check_pipeline_status.sh $PID"
}

# Handle commands
if [ -z "$COMMAND" ] || [ "$COMMAND" == "list" ]; then
    list_all_pipelines
    exit 0
fi

if [ "$COMMAND" == "cancel" ]; then
    cancel_pipeline "$PIPELINE_ID"
    exit 0
fi

if [ "$COMMAND" == "status" ] || [[ "$COMMAND" == pipeline_* ]]; then
    PIPELINE_ID=${PIPELINE_ID:-$COMMAND}
fi

if [ -z "$PIPELINE_ID" ]; then
    echo "Usage:"
    echo "  ./check_pipeline_status.sh                    # List all pipelines"
    echo "  ./check_pipeline_status.sh <pipeline_id>      # Check specific pipeline"
    echo "  ./check_pipeline_status.sh cancel <pipeline_id>  # Cancel a pipeline"
    exit 1
fi

echo "==========================================="
echo "Pipeline Status Check (Direct from Redis)"
echo "==========================================="
echo "Pipeline ID: $PIPELINE_ID"
echo ""

# Check if pipeline exists
EXISTS=$(docker exec redis redis-cli EXISTS "pipeline:$PIPELINE_ID:meta")

if [ "$EXISTS" -eq "0" ]; then
    echo "❌ Pipeline not found or expired"
    echo ""
    echo "Available pipelines:"
    docker exec redis redis-cli KEYS "pipeline:*:meta" | sed 's/pipeline://g' | sed 's/:meta//g' | sort -u | head -10
    exit 1
fi

# Get metadata
echo "📊 Pipeline Metadata:"
echo "-------------------------------------------"
docker exec redis redis-cli HGETALL "pipeline:$PIPELINE_ID:meta" | paste - - | column -t -s $'\t'
echo ""

# Get status
STATUS=$(docker exec redis redis-cli HGET "pipeline:$PIPELINE_ID:meta" status)
echo "📌 Current Status: $STATUS"
echo ""

# Check if result exists
RESULT_EXISTS=$(docker exec redis redis-cli EXISTS "pipeline:$PIPELINE_ID:result")

if [ "$RESULT_EXISTS" -eq "1" ]; then
    echo "✅ Result available! You can retrieve it via API:"
    echo "   GET /api/doc_gen/generation-result/$PIPELINE_ID"
    echo ""
    echo "📄 Result Summary:"
    echo "-------------------------------------------"
    docker exec redis redis-cli HGETALL "pipeline:$PIPELINE_ID:result" | paste - - | grep -E "(title|total_|status|completed)" | column -t -s $'\t'
else
    if [ "$STATUS" = "completed" ]; then
        echo "⚠️  Status is 'completed' but result not found. Generation may have failed."
    elif [ "$STATUS" = "processing" ]; then
        echo "⏳ Generation in progress. Result will be available when completed."
    elif [ "$STATUS" = "queued" ]; then
        echo "⏳ Generation queued. Waiting to start..."
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ Generation failed. Check error in metadata above."
    fi
fi

echo ""
echo "==========================================="
echo "To retrieve result when ready:"
echo "curl http://localhost:9020/api/doc_gen/generation-result/$PIPELINE_ID"
echo "==========================================="
