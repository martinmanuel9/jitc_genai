# Installation Guide

## Table of Contents
- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [Windows Installation](#windows-installation)
- [Linux Installation](#linux-installation)
- [macOS Installation](#macos-installation)
- [Post-Installation Configuration](#post-installation-configuration)
- [Updating](#updating)
- [Uninstallation](#uninstallation)
- [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **CPU:** 4 cores
- **RAM:** 8 GB
- **Disk Space:** 50 GB available
- **Operating Systems:**
  - Windows 10/11 (64-bit)
  - Ubuntu 20.04+ / Debian 11+
  - RHEL 8+ / CentOS 8+ / Fedora 35+
  - macOS 11 (Big Sur) or later

### Required Software
- **Docker:** 24.0.0 or later
- **Docker Compose:** 2.20.0 or later

### Optional (for local model support)
- **Ollama:** Latest version
- **NVIDIA GPU:** For accelerated inference (optional)
- **NVIDIA Docker:** For GPU support in containers

## Quick Start

### 1. Download Installer

Download the appropriate installer for your operating system from the [Releases](https://github.com/martinmanuel9/jitc_genai/releases) page:

- **Windows:** `genai-research-{version}.msi`
- **Ubuntu/Debian:** `genai-research_{version}_amd64.deb`
- **RHEL/CentOS/Fedora:** `genai-research-{version}.x86_64.rpm`
- **macOS:** `genai-research-{version}.dmg`

### 2. Verify Download (Optional but Recommended)

```bash
# Download checksums file
wget https://github.com/martinmanuel9/jitc_genai/releases/download/v{version}/checksums-sha256.txt

# Verify checksum
sha256sum -c checksums-sha256.txt --ignore-missing
```

### 3. Install

Follow the platform-specific instructions below.

---

## Windows Installation

### Prerequisites

1. **Install Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop
   - Minimum version: 24.0.0
   - Ensure WSL 2 is enabled

2. **Verify Docker is Running**
   ```powershell
   docker --version
   docker compose version
   ```

### Installation Steps

1. **Run Prerequisites Check (Optional)**
   ```powershell
   # Download and run the check script
   .\installer\windows\scripts\check_prerequisites.ps1
   ```

2. **Install via MSI**
   - Double-click `genai-research-{version}.msi`
   - Follow the installation wizard
   - Choose installation directory (default: `C:\Program Files\GenAI Research`)
   - Optionally create desktop shortcut

3. **Configure Environment**
   - Navigate to installation directory
   - Copy `.env.template` to `.env`
   - Edit `.env` with your API keys:
     ```
     OPENAI_API_KEY=your-key-here
     ```

4. **Start Services**
   ```powershell
   cd "C:\Program Files\GenAI Research"
   docker compose up -d
   ```

5. **Access Web Interface**
   - Open browser to: http://localhost:8501

### Post-Installation (Windows)

**Create Desktop Shortcut:**
The installer creates shortcuts in:
- Start Menu: `GenAI Research`
- Desktop: `GenAI Research` (if selected)

**Enable Auto-Start (Optional):**
```powershell
# Create scheduled task to start on login
schtasks /create /tn "GenAI Research" /tr "docker compose -f 'C:\Program Files\GenAI Research\docker-compose.yml' up -d" /sc onlogon
```

---

## Linux Installation

### Debian/Ubuntu

#### Prerequisites

1. **Install Docker**
   ```bash
   # Add Docker's official GPG key
   sudo apt-get update
   sudo apt-get install ca-certificates curl
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   sudo chmod a+r /etc/apt/keyrings/docker.asc

   # Add Docker repository
   echo \
     "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
     $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
     sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

   # Install Docker
   sudo apt-get update
   sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   ```

2. **Verify Docker**
   ```bash
   sudo docker --version
   sudo docker compose version
   ```

#### Installation Steps

1. **Run Prerequisites Check**
   ```bash
   chmod +x installer/scripts/check_prerequisites.sh
   ./installer/scripts/check_prerequisites.sh
   ```

2. **Install DEB Package**
   ```bash
   sudo dpkg -i genai-research_{version}_amd64.deb
   # Install any missing dependencies
   sudo apt-get install -f
   ```

3. **Configure Environment**
   ```bash
   sudo /opt/jitc_genai/scripts/setup-env.sh
   ```

4. **Start Services**
   ```bash
   sudo systemctl start jitc_genai
   sudo systemctl status jitc_genai
   ```

5. **Enable Auto-Start (Optional)**
   ```bash
   sudo systemctl enable jitc_genai
   ```

6. **Access Web Interface**
   - Open browser to: http://localhost:8501

### RHEL/CentOS/Fedora

#### Prerequisites

1. **Install Docker**
   ```bash
   # Add Docker repository
   sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo

   # Install Docker
   sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin

   # Start Docker
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

#### Installation Steps

1. **Install RPM Package**
   ```bash
   sudo rpm -i genai-research-{version}.x86_64.rpm
   ```

2. **Follow Post-Install Steps**
   Same as Debian/Ubuntu steps 3-6 above.

---

## macOS Installation

### Prerequisites

1. **Install Docker Desktop for Mac**
   - Download from: https://www.docker.com/products/docker-desktop
   - Minimum version: 24.0.0
   - Install and start Docker Desktop

2. **Verify Docker**
   ```bash
   docker --version
   docker compose version
   ```

### Installation Steps

1. **Run Prerequisites Check**
   ```bash
   chmod +x installer/scripts/check_prerequisites.sh
   ./installer/scripts/check_prerequisites.sh
   ```

2. **Install DMG**
   - Open `genai-research-{version}.dmg`
   - Drag `GenAI Research.app` to Applications folder
   - Eject DMG

3. **Configure Environment**
   ```bash
   # Open terminal in application directory
   cd "/Applications/GenAI Research.app/Contents/Resources"

   # Run setup wizard
   ./scripts/setup-env.sh
   ```

4. **Start Application**
   - Double-click `GenAI Research.app` in Applications
   - Or via terminal:
     ```bash
     cd "/Applications/GenAI Research.app/Contents/Resources"
     docker compose up -d
     ```

5. **Access Web Interface**
   - Open browser to: http://localhost:8501

---

## Post-Installation Configuration

### 1. Configure API Keys

Edit the `.env` file in your installation directory:

#### For Cloud Models (OpenAI)
```bash
OPENAI_API_KEY=sk-...your-key-here
```

#### For LangSmith Tracing (Optional)
```bash
LANGCHAIN_API_KEY=lsv2_pt_...your-key-here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=your-project-name
```

### 2. Install Ollama for Local Models (Optional)

Ollama provides local LLM support for privacy-sensitive environments and offline use.

#### Step 1: Install Ollama

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
# Or download from https://ollama.com/download/mac
```

**Windows:**
- Download from: https://ollama.com/download/windows
- Run the installer

#### Step 2: Start Ollama Server

**IMPORTANT:** You must start the Ollama server before pulling or using models.

**IMPORTANT:** For Docker containers to access Ollama, it must listen on all interfaces (0.0.0.0), not just localhost.

**Linux/macOS:**
```bash
# Start Ollama server listening on all interfaces (required for Docker)
OLLAMA_HOST=0.0.0.0:11434 ollama serve &

# Wait a few seconds for it to start
sleep 5

# Verify it's running
curl http://localhost:11434/api/tags
```

**Windows (PowerShell):**
```powershell
# Start Ollama server listening on all interfaces (required for Docker)
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve

# Or in one line (opens in new window)
Start-Process powershell -ArgumentList "-Command", "`$env:OLLAMA_HOST='0.0.0.0:11434'; ollama serve"
```

#### Step 3: Pull Models

**IMPORTANT:** Open a NEW terminal window (keep the server running) to pull models.

**Pull recommended text models for chat/generation (~9 GB):**
```bash
# Linux
/opt/jitc_genai/scripts/pull-ollama-models.sh recommended

# macOS
/Applications/GenAI\ Research.app/Contents/Resources/scripts/pull-ollama-models.sh recommended

# Windows (in new PowerShell window)
& "C:\Program Files\GenAI Research\scripts\pull-ollama-models.ps1" -Mode recommended
```

**Pull vision models for image understanding (~14.5 GB):**

Includes: `granite3.2-vision:2b`, `llava:7b`, `llava:13b`

```bash
# Linux
/opt/jitc_genai/scripts/pull-ollama-models.sh vision

# macOS
/Applications/GenAI\ Research.app/Contents/Resources/scripts/pull-ollama-models.sh vision

# Windows (in new PowerShell window)
& "C:\Program Files\GenAI Research\scripts\pull-ollama-models.ps1" -Mode vision
```

**Manual model pull (alternative):**
```bash
# Text models
ollama pull llama3.1:8b          # Recommended general model (4.7 GB)
ollama pull llama3.2:3b          # Lightweight model (2 GB)
ollama pull phi3:mini            # Microsoft's efficient model (2.3 GB)

# Vision models (for image understanding)
ollama pull granite3.2-vision:2b      # IBM Granite Vision - lightweight (1.5 GB)
ollama pull llava:7b                  # LLaVA 1.6 7B - vision-language model (4.7 GB)
ollama pull llava:13b                 # LLaVA 1.6 13B - larger multimodal (8 GB)
```

#### Step 4: Verify Models

```bash
# List installed models
ollama list

# Test a model
ollama run llama3.1:8b "Hello, how are you?"
```

#### Auto-Start on Boot (Optional)

**Linux (systemd):**
The Ollama installer automatically sets up a systemd service. After a reboot, Ollama should start automatically.
```bash
# Check service status
sudo systemctl status ollama

# Enable if not enabled
sudo systemctl enable ollama
```

**Windows:**
Ollama typically runs as a background app. You can add it to Windows Startup apps.

**macOS:**
```bash
# Add to login items via System Preferences > Users & Groups > Login Items
```

### 3. Verify Installation

**Check all services are running:**
```bash
# Linux/macOS
docker compose ps

# Windows
cd "C:\Program Files\GenAI Research"
docker compose ps
```

You should see 6 services running:
- `fastapi` - REST API backend
- `streamlit` - Web UI
- `postgres` - Database
- `chromadb` - Vector store
- `redis` - Cache
- `celery-worker` - Background tasks

**Test the web interface:**
- Navigate to: http://localhost:8501
- You should see the GenAI Research home page

---

## Updating

### Check Current Version

**Linux:**
```bash
cat /opt/jitc_genai/VERSION
```

**Windows:**
```powershell
Get-Content "C:\Program Files\GenAI Research\VERSION"
```

**macOS:**
```bash
cat "/Applications/GenAI Research.app/Contents/Resources/VERSION"
```

### Update to New Version

1. **Stop Current Services**
   ```bash
   # Linux
   sudo systemctl stop jitc_genai

   # Windows/macOS
   docker compose down
   ```

2. **Backup Data (Recommended)**
   ```bash
   # Linux
   sudo cp -r /var/lib/jitc_genai /var/lib/jitc_genai.backup

   # Windows
   docker compose exec postgres pg_dump -U g3nA1-user rag_memory > backup.sql

   # macOS
   docker compose exec postgres pg_dump -U g3nA1-user rag_memory > backup.sql
   ```

3. **Install New Version**
   - Download new installer
   - Install over existing installation
   - Installer will preserve your `.env` configuration and data

4. **Restart Services**
   ```bash
   # Linux
   sudo systemctl start jitc_genai

   # Windows/macOS
   docker compose up -d
   ```

---

## Uninstallation

### Windows

1. **Stop Services**
   ```powershell
   cd "C:\Program Files\GenAI Research"
   docker compose down
   ```

2. **Uninstall via Control Panel**
   - Open "Add or Remove Programs"
   - Find "GenAI Research"
   - Click "Uninstall"

3. **Remove Data (Optional)**
   ```powershell
   # Remove Docker volumes
   docker volume rm genai_postgres_data genai_chroma_data genai_hf_cache genai_redis_data
   ```

### Linux

1. **Stop Services**
   ```bash
   sudo systemctl stop jitc_genai
   sudo systemctl disable jitc_genai
   ```

2. **Uninstall Package**
   ```bash
   # Debian/Ubuntu
   sudo dpkg --purge genai-research

   # RHEL/CentOS/Fedora
   sudo rpm -e genai-research
   ```

3. **Remove Data (If Prompted)**
   The uninstaller will ask if you want to remove data at `/var/lib/jitc_genai`

### macOS

1. **Stop Services**
   ```bash
   cd "/Applications/GenAI Research.app/Contents/Resources"
   docker compose down
   ```

2. **Remove Application**
   - Drag `GenAI Research.app` to Trash
   - Empty Trash

3. **Remove Data (Optional)**
   ```bash
   rm -rf ~/Library/Application\ Support/GenAI\ Research
   docker volume rm genai_postgres_data genai_chroma_data genai_hf_cache genai_redis_data
   ```

---

## Troubleshooting

### Services Won't Start

**Check Docker is running:**
```bash
docker info
```

**Check port conflicts:**
```bash
# Linux/macOS
sudo lsof -i :8501
sudo lsof -i :9020

# Windows
netstat -ano | findstr :8501
netstat -ano | findstr :9020
```

**View service logs:**
```bash
docker compose logs -f
```

### Can't Access Web Interface

1. **Verify services are running:**
   ```bash
   docker compose ps
   ```

2. **Check Streamlit logs:**
   ```bash
   docker compose logs streamlit
   ```

3. **Try accessing directly:**
   ```bash
   curl http://localhost:8501
   ```

### Database Connection Errors

**Check PostgreSQL is running:**
```bash
docker compose ps postgres
docker compose logs postgres
```

**Verify credentials in `.env`:**
```bash
grep DB_PASSWORD .env
```

### Ollama Models Not Available

1. **Check Ollama is running:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. **Verify Ollama configuration:**
   ```bash
   # Linux
   sudo systemctl status ollama

   # Check listening address
   ps aux | grep ollama
   ```

3. **Pull models if missing:**
   ```bash
   ./scripts/pull-ollama-models.sh auto
   ```

### Permission Denied Errors (Linux)

**Add user to docker group:**
```bash
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

### Out of Disk Space

**Check disk usage:**
```bash
df -h
docker system df
```

**Clean up Docker:**
```bash
docker system prune -a --volumes
```

### Get Help

- **Documentation:** https://github.com/martinmanuel9/jitc_genai
- **Issues:** https://github.com/martinmanuel9/jitc_genai/issues
- **Email:** support@example.com

---

## Next Steps

After successful installation:

1. **Read the User Guide:** See `README.md` for feature documentation
2. **Upload Test Documents:** Use the Upload Documents tab
3. **Generate Test Plans:** Navigate to Document Generator
4. **Explore AI Features:** Try AI Simulation and Chat
5. **Configure Models:** Select between cloud and local models based on your needs

Enjoy using GenAI Research!
