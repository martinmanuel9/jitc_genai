# Quick Start Guide - Windows Installer

## Installation

### Step 1: Run the MSI Installer
Double-click `dis-verification-genai-X.X.X.msi`

### Step 2: Accept the MIT License
Read and accept the MIT License to continue

### Step 3: Configure Environment (NEW!)
You'll see an "Environment Configuration" dialog with two options:

#### Option A: Paste .env Contents Now
**Choose this if:** You have an existing .env file from another installation

1. Copy your entire .env file contents
2. Select "Paste .env file contents now"
3. Paste into the text field
4. Click Next

#### Option B: Configure Later (Recommended)
**Choose this if:** You're a new user or want guided setup

1. Select "Configure environment later (recommended for new users)"
2. Click Next
3. The interactive wizard will run after installation

### Step 4: Choose Installation Directory
Default: `C:\Program Files\GenAI Research`

### Step 5: Complete Installation
Click Install and wait for completion

### Step 6: Post-Installation Setup
If you selected "Run first-time setup wizard":

1. Docker Desktop check (will prompt to start if not running)
2. Environment configuration wizard (if you chose "Configure later")
3. Optional Ollama installation
4. Option to start the application immediately

## Quick Actions

### From Start Menu:
- **GenAI Research** - Start the application
- **Configure Environment** - Reconfigure .env settings
- **First-Time Setup** - Run complete setup wizard
- **Stop Services** - Stop all Docker containers

### From Desktop:
- **GenAI Research** - Start the application (if you enabled desktop shortcut)

## Configuration Options

### If You Have an Existing .env File:

Run "Configure Environment" from Start Menu, then choose:

1. **Keep existing** - Don't make any changes
2. **Reconfigure interactively** - Answer prompts to rebuild configuration
3. **Paste contents** - Copy/paste from another .env file
4. **Browse for file** - Select an .env file using file browser

### If This Is Your First Installation:

The interactive wizard will ask for:

1. **OpenAI API Key** (optional, for cloud models)
   - Get from: https://platform.openai.com/api-keys
   - Press Enter to skip

2. **Ollama Model Selection** (if Ollama installed)
   - llama3.2:1b (lightweight, 1.3 GB)
   - llama3.1:8b (recommended, 4.7 GB)
   - None (configure later)

3. **Database Password**
   - Auto-generated secure password (recommended)
   - Or enter your own

4. **LangSmith Tracing** (optional)
   - For debugging and monitoring
   - Requires LangSmith account

## Starting the Application

### Method 1: Start Menu Shortcut
Click "GenAI Research" from Start Menu
- Starts Docker containers
- Opens web browser to http://localhost:8501

### Method 2: Command Line
```cmd
cd "C:\Program Files\GenAI Research"
docker compose up -d
start http://localhost:8501
```

## Accessing the Application

Once started, access via:
- **Web UI**: http://localhost:8501 (Streamlit)
- **API**: http://localhost:9020 (FastAPI)

## Stopping the Application

### Method 1: Start Menu
Click "Stop Services" from Start Menu

### Method 2: Command Line
```cmd
cd "C:\Program Files\GenAI Research"
docker compose down
```

## Troubleshooting

### Docker Not Running
**Error**: "Docker Desktop is not running"
**Solution**:
1. Start Docker Desktop
2. Wait for it to fully start (green icon in system tray)
3. Retry starting the application

### Missing .env File
**Error**: Container fails to start with environment errors
**Solution**:
1. Run "Configure Environment" from Start Menu
2. Complete the configuration wizard
3. Restart the application

### Port Already in Use
**Error**: "Port 8501 is already in use"
**Solution**:
1. Stop other services using that port
2. Or edit docker-compose.yml to use different ports

### API Key Invalid
**Error**: "Authentication failed" or "Invalid API key"
**Solution**:
1. Run "Configure Environment" from Start Menu
2. Choose option 2 (Reconfigure interactively)
3. Enter correct API key
4. Restart the application

## Getting Help

### Log Files
- Installation log: `%TEMP%\dis-genai-install.log`
- Application logs: Check Docker logs
  ```cmd
  cd "C:\Program Files\GenAI Research"
  docker compose logs
  ```

### Documentation
- Installation Guide: `INSTALL.md` in installation directory
- Environment Configuration: `ENV_CONFIGURATION.md` in installer/windows
- README: `README.md` in installation directory

### Support
- GitHub Issues: https://github.com/martinmanuel9/jitc_genai/issues
- Repository: https://github.com/martinmanuel9/jitc_genai

## Upgrading

### From Previous Version:
1. Run new MSI installer
2. Your existing .env configuration will be preserved
3. Choose "Keep existing configuration" in post-install wizard
4. Or reconfigure if needed

### Fresh Install:
1. Stop the application
2. Uninstall from Windows Settings > Apps
3. Delete installation directory if desired
4. Run new MSI installer

## Uninstalling

1. Stop the application (Stop Services from Start Menu)
2. Windows Settings > Apps
3. Find "GenAI Research"
4. Click Uninstall

**Note**: Docker images and volumes are preserved. To remove them:
```cmd
docker image rm dis-verification-genai-*
docker volume rm dis-verification-genai_*
```

## Next Steps

After installation and first start:

1. **Configure API Keys** (if skipped during setup)
   - Edit .env file directly
   - Or run "Configure Environment"

2. **Pull Ollama Models** (for local AI)
   - Install Ollama: https://ollama.com/download/windows
   - Pull models: `ollama pull llama3.1:8b`

3. **Explore the Application**
   - Upload documents
   - Generate test plans
   - Try different AI models

4. **Read the Documentation**
   - Check README.md for features
   - Review INSTALL.md for advanced configuration

---

**Welcome to GenAI Research!**

For more information, visit: https://github.com/martinmanuel9/jitc_genai
