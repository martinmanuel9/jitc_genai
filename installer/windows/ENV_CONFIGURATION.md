# Environment Configuration in Windows Installer

The Windows MSI installer now includes multiple ways to configure the `.env` file during and after installation.

## During Installation

### Option 1: Paste .env Contents During Installation

When running the MSI installer, you'll be presented with an "Environment Configuration" dialog after accepting the license agreement. This dialog allows you to:

1. **Paste .env file contents now**: Select this option if you already have a configured `.env` file
   - Copy your entire `.env` file contents
   - Paste them into the text field provided
   - The installer will create the `.env` file with your provided content

2. **Configure environment later** (recommended for new users): Select this option to use the interactive setup wizard after installation
   - This is the default and recommended option for first-time users
   - The interactive wizard will guide you through the configuration step-by-step

### How the .env File is Created

The installer uses the custom PowerShell script `create-env-from-input.ps1` which:

1. If user provided content during installation:
   - Creates `.env` file from the pasted content
   - Validates the file was created successfully

2. If no content was provided:
   - Copies from `.env.template` if available
   - Or creates a minimal `.env` file with default values

## After Installation

### Interactive Setup Wizard

The post-installation script (`post-install.ps1`) will prompt you to run the interactive environment setup wizard. This wizard (`setup-env.ps1`) provides multiple options:

#### For New Installations:
- Guided configuration with prompts for:
  - OpenAI API Key
  - Ollama model selection
  - Database password (auto-generated or custom)
  - LangSmith tracing (optional)

#### For Existing .env Files:
If a `.env` file already exists, you'll see these options:

1. **Keep existing configuration** - Exit without changes
2. **Reconfigure interactively** - Use the guided wizard to reconfigure
3. **Import from .env file (paste contents)** - Manually paste new `.env` content
   - Paste your content line by line
   - Type `END` on a new line when finished
   - The old configuration will be backed up
4. **Import from .env file (select file)** - Browse and select an existing `.env` file
   - Opens a file browser dialog
   - Select your `.env` file
   - The old configuration will be backed up

### Manual Configuration Options

#### From Start Menu:
- **Configure Environment** shortcut: Opens the interactive setup wizard
- **First-Time Setup** shortcut: Runs the complete post-installation wizard

#### From Command Line:
```powershell
# Run the interactive environment setup
powershell -ExecutionPolicy Bypass -File "C:\Program Files\GenAI Research\scripts\setup-env.ps1"

# Or with custom install directory
powershell -ExecutionPolicy Bypass -File "C:\Program Files\GenAI Research\scripts\setup-env.ps1" -InstallDir "C:\Your\Custom\Path"
```

## Configuration Backup

All reconfiguration operations automatically create timestamped backups:
- Format: `.env.backup.YYYYMMDD_HHMMSS`
- Located in the installation directory
- Allows you to restore previous configurations if needed

## Required Configuration Values

At minimum, your `.env` file should include:

```env
# API Keys (at least one is recommended)
OPENAI_API_KEY=your_key_here

# Database Configuration
DATABASE_URL=postgresql://g3nA1-user:your_password@postgres:5432/rag_memory
DB_PASSWORD=your_password

# Service URLs (usually don't need to change)
FASTAPI_URL=http://fastapi:9020
CHROMA_URL=http://chromadb:8001
REDIS_URL=redis://redis:6379/0

# Ollama Configuration
OLLAMA_URL=http://host.docker.internal:11434
```

## Troubleshooting

### .env File Not Created
Check the installation log at: `%TEMP%\dis-genai-install.log`

### Configuration Script Errors
The setup scripts log errors to the console. Common issues:
- Missing `.env.template` file
- Insufficient permissions in installation directory
- PowerShell execution policy restrictions

### Starting Fresh
To completely reconfigure:
1. Delete or rename the existing `.env` file
2. Run the setup wizard from the Start Menu or command line
3. The wizard will start with a clean configuration

## License

This installer includes the MIT License, which is displayed during installation.

For more information, see the main repository:
https://github.com/martinmanuel9/jitc_genai
