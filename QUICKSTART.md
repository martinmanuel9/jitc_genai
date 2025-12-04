# Quick Start Guide

Get GenAI Research running in 10 minutes!

## Step 1: Download Installer

Visit the [Releases page](https://github.com/martinmanuel9/jitc_genai/releases) and download the installer for your operating system:

| Operating System | File to Download |
|-----------------|------------------|
| **Windows 10/11** | `genai-research-{version}.msi` |
| **Ubuntu/Debian** | `genai-research_{version}_amd64.deb` |
| **RHEL/CentOS/Fedora** | `genai-research-{version}.x86_64.rpm` |
| **macOS** | `genai-research-{version}.dmg` |

**Current Version:** Check the VERSION file or latest release tag

## Step 2: Install Prerequisites

### Windows
1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. Enable WSL 2 during installation
3. Start Docker Desktop

### Linux
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Log out and back in

# RHEL/CentOS/Fedora
sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
```

### macOS
1. Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. Start Docker Desktop from Applications

## Step 3: Install GenAI Research

### Windows
1. Double-click the `.msi` file
2. Follow the installation wizard
3. Choose installation directory
4. Click "Install"

### Ubuntu/Debian
```bash
sudo dpkg -i genai-research_{version}_amd64.deb
sudo apt-get install -f  # Install any missing dependencies
```

### RHEL/CentOS/Fedora
```bash
sudo rpm -i genai-research-{version}.x86_64.rpm
```

### macOS
1. Open the `.dmg` file
2. Drag "GenAI Research" to Applications
3. Eject the disk image

## Step 4: Configure

### Windows
1. Navigate to: `C:\Program Files\GenAI Research`
2. Edit `.env` file with Notepad (Run as Administrator)
3. Add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-...your-key-here
   ```
4. Save and close

### Linux
```bash
sudo /opt/jitc_genai/scripts/setup-env.sh
```
Follow the interactive prompts to configure API keys and settings.

### macOS
```bash
cd "/Applications/GenAI Research.app/Contents/Resources"
./scripts/setup-env.sh
```

## Step 5: Start the Application

### Windows
- Use the Start Menu shortcut: "GenAI Research"
- Or run from Command Prompt:
  ```cmd
  cd "C:\Program Files\GenAI Research"
  docker compose up -d
  ```

### Linux
```bash
sudo systemctl start jitc_genai
sudo systemctl enable jitc_genai  # Auto-start on boot
```

### macOS
- Double-click "GenAI Research" in Applications
- Or from Terminal:
  ```bash
  cd "/Applications/GenAI Research.app/Contents/Resources"
  docker compose up -d
  ```

## Step 6: Access the Web Interface

Open your browser to: **http://localhost:8501**

You should see the GenAI Research home page!

## Step 7 (Optional): Install Local Models

For on-premises AI models (no internet required):

### Linux
```bash
sudo /opt/jitc_genai/scripts/install-ollama.sh
/opt/jitc_genai/scripts/pull-ollama-models.sh auto
```

### macOS
```bash
brew install ollama
cd "/Applications/GenAI Research.app/Contents/Resources"
./scripts/pull-ollama-models.sh auto
```

### Windows
1. Download Ollama from https://ollama.com/download/windows
2. Install and start Ollama
3. Open Command Prompt and run:
   ```cmd
   cd "C:\Program Files\GenAI Research\scripts"
   bash pull-ollama-models.sh auto
   ```

## What's Next?

### Upload Your First Document
1. Click "Upload Documents" tab
2. Upload a PDF, DOCX, or TXT file
3. Wait for processing to complete

### Generate a Test Plan
1. Click "Document Generator" tab
2. Select your uploaded document
3. Choose AI model (GPT-4o recommended)
4. Click "Generate Test Plan"
5. Download as Word document when complete

### Try AI Chat
1. Click "Chat" tab
2. Select a model
3. Ask questions about your documents

## Need Help?

- **Full Documentation:** See [INSTALL.md](INSTALL.md)
- **User Guide:** See [README.md](README.md)
- **Issues:** https://github.com/martinmanuel9/jitc_genai/issues
- **Email Support:** support@example.com

## Common Issues

### "Cannot connect to Docker daemon"
**Solution:** Make sure Docker Desktop is running
- Windows/Mac: Check system tray/menu bar for Docker icon
- Linux: `sudo systemctl start docker`

### "Port already in use"
**Solution:** Another application is using the same port
```bash
# Find and stop the conflicting service
# Linux/Mac
sudo lsof -i :8501
# Windows
netstat -ano | findstr :8501
```

### "No models available"
**Solution:** Configure your API keys in the `.env` file

### Services won't start
**Solution:** Check logs
```bash
# Navigate to installation directory
docker compose logs -f
```

## Checking Version

Your installed version is shown in the web interface footer.

To check from command line:

**Linux:**
```bash
cat /opt/jitc_genai/VERSION
```

**Windows:**
```cmd
type "C:\Program Files\GenAI Research\VERSION"
```

**macOS:**
```bash
cat "/Applications/GenAI Research.app/Contents/Resources/VERSION"
```

## Updating

When a new version is released:

1. Download the new installer
2. Run the installer (it will upgrade automatically)
3. Your data and configuration will be preserved

---

**Congratulations!** You're ready to use GenAI Research! 🚀
