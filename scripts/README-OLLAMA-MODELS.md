# Ollama Model Auto-Pull Script

## Overview

This script automatically detects your system's GPU capabilities and pulls the optimal US-based Ollama models for your hardware configuration.

**All models are from US-based organizations only:**
- 🏢 **Meta** (California) - Llama 3.2, Llama 3.1, Llama 3 series
- 🏢 **Microsoft** (Washington) - Phi-3 series
- 🏢 **Snowflake** (Montana) - Arctic Embed series

## Quick Start

### Auto Mode (Recommended)
Let the script detect your GPU and select optimal models:
```bash
./scripts/pull-ollama-models.sh
# or explicitly:
./scripts/pull-ollama-models.sh auto
```

### Manual Modes
Override auto-detection and manually select model sets:

```bash
# Lightweight (6.6 GB) - Best for CPU-only or testing
./scripts/pull-ollama-models.sh quick

# Production (9 GB) - Balanced performance
./scripts/pull-ollama-models.sh recommended

# Full Suite (90+ GB) - Everything including 70B models
./scripts/pull-ollama-models.sh full

# Embeddings Only - For RAG and semantic search
./scripts/pull-ollama-models.sh embeddings
```

## How Auto Detection Works

The script detects your hardware and recommends models based on available resources:

### 1. **CPU-Only or No GPU** (Tier 1)
**Models Pulled:**
- `llama3.2:1b` - Meta's smallest (1.3 GB)
- `llama3.2:3b` - Meta's balanced (2 GB)
- `phi3:mini` - Microsoft's efficient (2.3 GB)
- `snowflake-arctic-embed2` - Embeddings (1.7 GB)

**Total Size:** ~5.6 GB

### 2. **Low VRAM: < 8 GB** (Tier 1)
**Models Pulled:**
- `llama3.2:3b` - Meta's balanced (2 GB)
- `phi3:mini` - Microsoft's efficient (2.3 GB)
- `snowflake-arctic-embed2` - Embeddings (1.7 GB)

**Total Size:** ~6.0 GB

### 3. **Moderate VRAM: 8-16 GB** (Tier 2)
**Models Pulled:**
- `llama3.2:3b` - Meta's balanced (2 GB)
- `llama3.1:8b` - Meta's powerful 8B (4.7 GB)
- `phi3:mini` - Microsoft's efficient (2.3 GB)
- `snowflake-arctic-embed2` - Embeddings (1.7 GB)

**Total Size:** ~10.7 GB

### 4. **High VRAM: 16-40 GB** (Tier 3)
**Models Pulled:**
- `llama3.1:8b` - Meta Llama 3.1 8B (4.7 GB)
- `llama3:8b` - Meta Llama 3 8B (4.7 GB)
- `phi3:mini` - Microsoft Phi-3 Mini (2.3 GB)
- `phi3:medium` - Microsoft Phi-3 Medium (7.9 GB)
- `snowflake-arctic-embed2` - Embeddings (1.7 GB)

**Total Size:** ~19.3 GB

### 5. **Enterprise VRAM: 40+ GB** (Tier 4)
**Models Available:**
- All 8B models
- `phi3:medium` (7.9 GB)
- **Optional:** `llama3.1:70b` and `llama3:70b` (40 GB each)

The script will prompt you to confirm before pulling 70B models due to their size.

## Virtual/Cloud GPU Handling

If your system has a virtual GPU (like NVIDIA GB10) that doesn't report VRAM:
- The script will detect the GPU but note VRAM is unavailable
- **Default behavior:** Pull Tier 2 (Balanced) models as a safe default
- You can override by using manual modes (quick/recommended/full)

**Example output:**
```
[WARNING] NVIDIA GPU detected: NVIDIA GB10 (Virtual/Cloud GPU - VRAM info unavailable)
  Note: Cannot determine exact VRAM, defaulting to balanced configuration

[INFO] VRAM information unavailable - Recommending balanced models
  Models: llama3.2:3b, llama3.1:8b, phi3:mini, snowflake-arctic-embed2
  Total Size: ~10.7 GB

  💡 Tip: You can override this by running:
     ./scripts/pull-ollama-models.sh quick      # For lightweight models
     ./scripts/pull-ollama-models.sh recommended # For production models
```

## Model Details

### Meta Llama Models

| Model | Size | Context Window | Best For |
|-------|------|----------------|----------|
| `llama3.2:1b` | 1.3 GB | 128K tokens | CPU inference, ultra-lightweight |
| `llama3.2:3b` | 2.0 GB | 128K tokens | Balanced performance, moderate resources |
| `llama3.1:8b` | 4.7 GB | 128K tokens | Complex tasks, production workloads |
| `llama3.1:70b` | 40 GB | 128K tokens | Enterprise-grade, highest quality |
| `llama3:8b` | 4.7 GB | 8K tokens | Stable, reliable performance |
| `llama3:70b` | 40 GB | 8K tokens | Large-scale tasks |

### Microsoft Phi Models

| Model | Size | Context Window | Best For |
|-------|------|----------------|----------|
| `phi3:mini` | 2.3 GB | 128K tokens | Efficient, excellent quality-to-size ratio |
| `phi3:medium` | 7.9 GB | 128K tokens | Enterprise use, strong performance |

### Snowflake Arctic Embed Models

| Model | Size | Context Window | Best For |
|-------|------|----------------|----------|
| `snowflake-arctic-embed` | 1.0 GB | 512 tokens | RAG, semantic search |
| `snowflake-arctic-embed2` | 1.7 GB | 8K tokens | Multilingual embeddings, superior English |

## Prerequisites

1. **Ollama must be installed:**
   ```bash
   # Check if installed
   which ollama

   # If not installed, visit: https://ollama.com/download
   ```

2. **Ollama service must be running:**
   ```bash
   # Check status
   sudo systemctl status ollama

   # Start if needed
   sudo systemctl start ollama
   ```

3. **Ollama must be accessible on localhost:11434:**
   ```bash
   # Test accessibility
   curl http://localhost:11434/api/tags
   ```

4. **(Optional) For GPU acceleration:**
   - NVIDIA GPU: `nvidia-smi` must be available
   - AMD GPU: `rocm-smi` must be available

## Usage Examples

### Example 1: First-time Setup (Auto Mode)
```bash
# Let the script detect your GPU and pull optimal models
./scripts/pull-ollama-models.sh

# Output will show:
# - GPU detection results
# - Recommended models based on hardware
# - Progress as each model downloads
# - Summary of installed models
```

### Example 2: Limited Resources (Quick Mode)
```bash
# Pull only the smallest, fastest models
./scripts/pull-ollama-models.sh quick

# Models: llama3.2:1b, llama3.2:3b, phi3:mini, snowflake-arctic-embed
# Total: ~6.6 GB
```

### Example 3: Production Deployment (Recommended Mode)
```bash
# Pull production-ready balanced models
./scripts/pull-ollama-models.sh recommended

# Models: llama3.2:3b, llama3.1:8b, phi3:mini, snowflake-arctic-embed2
# Total: ~9 GB
```

### Example 4: Embeddings for RAG Only
```bash
# Pull only embedding models for RAG applications
./scripts/pull-ollama-models.sh embeddings

# Models: snowflake-arctic-embed, snowflake-arctic-embed2
# Total: ~2.7 GB
```

### Example 5: Everything (Full Mode)
```bash
# Pull all available US-based models including 70B variants
./scripts/pull-ollama-models.sh full

# Will prompt for confirmation due to size (90+ GB total)
# Models: All Llama, Phi, and Snowflake models
```

## After Pulling Models

### 1. Verify Models Are Available
```bash
ollama list
```

You should see all pulled models listed.

### 2. Test a Model
```bash
# Test with an interactive chat
ollama run llama3.1:8b

# Type your question and press Enter
# Type /bye to exit
```

### 3. Configure Ollama for Docker Access

Your Docker containers need to access Ollama on the host. Ensure Ollama is listening on `0.0.0.0:11434`:

```bash
# Create systemd override
sudo mkdir -p /etc/systemd/system/ollama.service.d/
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Verify it's listening on all interfaces
curl http://localhost:11434/api/tags
```

### 4. Use Models in Application

Models are now available in:
- **Streamlit UI:** Select from model dropdown menus
- **FastAPI:** Available via `/api/chat` endpoint
- **Direct API calls:** Use model IDs like `llama3.1:8b`

## Troubleshooting

### Issue: "Ollama is not installed"
**Solution:** Install Ollama from https://ollama.com/download

### Issue: "Ollama service is not running"
**Solution:**
```bash
sudo systemctl start ollama
sudo systemctl status ollama
```

### Issue: "Failed to pull model"
**Possible causes:**
1. No internet connection
2. Insufficient disk space
3. Ollama service crashed during download

**Solution:**
```bash
# Check disk space
df -h

# Check Ollama service
sudo systemctl status ollama

# Retry pulling the specific model
ollama pull llama3.1:8b
```

### Issue: GPU not detected but you have one
**Solution:**
1. Check if NVIDIA drivers are installed: `nvidia-smi`
2. If using AMD: Check if ROCm is installed: `rocm-smi`
3. Use manual mode as a workaround: `./scripts/pull-ollama-models.sh recommended`

### Issue: Virtual GPU shows 0 GB VRAM
**This is expected behavior.** Virtual/cloud GPUs often don't report VRAM.
- The script defaults to balanced models (Tier 2)
- Override if needed: `./scripts/pull-ollama-models.sh quick` or `./scripts/pull-ollama-models.sh recommended`

## Model Selection Guide

### Choose Based on Your Use Case:

**Quick Testing / Development:**
- Use: `./scripts/pull-ollama-models.sh quick`
- Models: 1B-3B parameters
- Fast inference, good for iterating

**Production / Critical Applications:**
- Use: `./scripts/pull-ollama-models.sh recommended`
- Models: 3B-8B parameters
- Balanced quality and speed

**Maximum Quality / Enterprise:**
- Use: `./scripts/pull-ollama-models.sh full`
- Models: Up to 70B parameters
- Best quality, requires powerful GPU

**RAG / Embeddings Only:**
- Use: `./scripts/pull-ollama-models.sh embeddings`
- Models: Snowflake Arctic Embed series
- Optimized for semantic search

## Model Updates

To update models to the latest versions:

```bash
# Re-run the pull script (it will update existing models)
./scripts/pull-ollama-models.sh auto

# Or update a specific model
ollama pull llama3.1:8b
```

## Disk Space Requirements

Make sure you have enough free disk space before pulling models:

| Mode | Disk Space Required |
|------|---------------------|
| Quick | ~7 GB |
| Recommended | ~10 GB |
| Auto (varies) | 6-20 GB depending on GPU |
| Full | ~100 GB |
| Embeddings | ~3 GB |

Check available space:
```bash
df -h /root/.ollama
```

## Security & Compliance

✅ **All models are from US-based organizations:**
- Meta (California)
- Microsoft (Washington)
- Snowflake (Montana)

✅ **All models run completely on-premises:**
- No data leaves your infrastructure
- No API keys required (unlike OpenAI, Anthropic)
- Full control over model execution

✅ **Models are open source:**
- Transparent model architectures
- Can audit model behavior
- No vendor lock-in

## Performance Tips

1. **Use GPU when available:** Models run 10-50x faster on GPU
2. **Start with smaller models:** Test with 3B/8B before trying 70B
3. **Monitor VRAM usage:** Use `nvidia-smi` to check GPU memory
4. **Use embeddings for RAG:** Snowflake Arctic Embed 2 is optimized for retrieval
5. **Adjust context window:** Smaller contexts = faster inference

## Support

For issues with:
- **Ollama installation:** https://ollama.com/download
- **Model performance:** Try different models from the recommended set
- **Docker connectivity:** Check OLLAMA_HOST configuration in docker-compose.yml
- **This script:** Contact your system administrator

## Version History

- **v2.0** - Added GPU auto-detection and "auto" mode (default)
- **v1.0** - Initial release with manual modes (quick/recommended/full/embeddings)
