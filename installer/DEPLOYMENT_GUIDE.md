# Deployment Guide for GenAI Research

## Overview

This guide explains how to deploy GenAI Research using the automated installer system.

## For End Users (Customers)

### Quick Install
1. Download installer from GitHub Releases
2. Run installer for your platform
3. Configure `.env` with API keys
4. Start services
5. Access web interface at http://localhost:8501

**See:** [QUICKSTART.md](../QUICKSTART.md) for detailed steps

**See:** [INSTALL.md](../INSTALL.md) for comprehensive installation guide

## For Developers/Maintainers

### Creating a New Release

#### 1. Prepare Release

```bash
# Update version
echo "1.2.0" > VERSION

# Update changelog
nano CHANGELOG.md
# Add release notes under [1.2.0] section

# Commit changes
git add VERSION CHANGELOG.md
git commit -m "Prepare release 1.2.0"
git push origin main
```

#### 2. Create and Push Tag

```bash
# Create annotated tag
git tag -a v1.2.0 -m "Release version 1.2.0"

# Push tag to trigger GitHub Actions
git push origin v1.2.0
```

#### 3. Monitor GitHub Actions

- Go to GitHub Actions tab
- Watch "Build Installers" workflow
- Wait for all build jobs to complete (~10-15 minutes)

#### 4. Verify Release

- Go to GitHub Releases
- Verify all installer files are present:
  - `dis-verification-genai-1.2.0.msi` (Windows)
  - `dis-verification-genai_1.2.0_amd64.deb` (Debian/Ubuntu)
  - `dis-verification-genai-1.2.0.x86_64.rpm` (RHEL/CentOS)
  - `dis-verification-genai-1.2.0.dmg` (macOS)
  - `checksums-sha256.txt`

#### 5. Test Installers

Download and test each installer on appropriate platforms before announcing release.

### Manual Release (Without Tag)

Use workflow_dispatch to build without creating a tag:

1. Go to GitHub Actions
2. Select "Build Installers"
3. Click "Run workflow"
4. Enter version number (e.g., "1.2.0-beta")
5. Click "Run workflow"

### Local Build for Testing

```bash
# Build all packages locally
./installer/build-local.sh all

# Test specific package
./installer/build-local.sh deb    # Debian package only
./installer/build-local.sh rpm    # RPM package only
./installer/build-local.sh dmg    # macOS package only (macOS only)
```

**Output:** Packages will be in `dist/` directory

## Installation Paths

### Windows
- **Application:** `C:\Program Files\GenAI Research`
- **Data:** `%PROGRAMDATA%\GenAI Research`
- **Start Menu:** `Start > GenAI Research`

### Linux
- **Application:** `/opt/dis-verification-genai`
- **Data:** `/var/lib/dis-verification-genai`
- **Service:** `systemctl {start|stop|status} dis-verification-genai`
- **Logs:** `journalctl -u dis-verification-genai -f`

### macOS
- **Application:** `/Applications/GenAI Research.app`
- **Data:** `~/Library/Application Support/GenAI Research`

## Configuration

### Environment Variables (.env)

All platforms use a `.env` file for configuration:

**Required:**
- `OPENAI_API_KEY` - For cloud AI models

**Optional:**
- `OLLAMA_MODELS` - Models to auto-pull on startup
- `LANGCHAIN_API_KEY` - For LangSmith tracing
- `DB_PASSWORD` - PostgreSQL password (auto-generated)

**See:** `.env.template` for full configuration options

### Service Configuration

#### Windows
Services start manually or via shortcuts. For auto-start:
```powershell
schtasks /create /tn "GenAI Research" /tr "docker compose up -d" /sc onlogon
```

#### Linux
Services managed by systemd:
```bash
sudo systemctl enable dis-verification-genai  # Auto-start on boot
sudo systemctl start dis-verification-genai   # Start now
sudo systemctl status dis-verification-genai  # Check status
```

#### macOS
Services start via application launcher or manually:
```bash
cd "/Applications/GenAI Research.app/Contents/Resources"
docker compose up -d
```

## Updating

### For End Users

1. Download new installer
2. Run installer (will upgrade automatically)
3. Configuration and data are preserved
4. Restart services if needed

### For Developers

Test upgrade path:
```bash
# Install old version
sudo dpkg -i dis-verification-genai_1.0.0_amd64.deb

# Upgrade to new version
sudo dpkg -i dis-verification-genai_1.1.0_amd64.deb

# Verify upgrade
cat /opt/dis-verification-genai/VERSION
docker compose ps
```

## Uninstallation

### Windows
1. Stop services: `docker compose down`
2. Control Panel > Add or Remove Programs
3. Uninstall "GenAI Research"
4. Optionally remove Docker volumes

### Linux
```bash
# Stop services
sudo systemctl stop dis-verification-genai

# Debian/Ubuntu
sudo dpkg --purge dis-verification-genai

# RHEL/CentOS
sudo rpm -e dis-verification-genai

# Remove data (optional)
sudo rm -rf /var/lib/dis-verification-genai
```

### macOS
1. Stop services: `docker compose down`
2. Drag app to Trash
3. Remove data: `rm -rf ~/Library/Application\ Support/DIS\ Verification\ GenAI`

## Troubleshooting

### Build Failures

**GitHub Actions fails:**
1. Check workflow logs in Actions tab
2. Verify VERSION file format (single line, no extra characters)
3. Ensure all source files are committed
4. Check syntax in WiX/DEB/RPM configurations

**Local build fails:**
1. Verify build tools are installed
2. Check file permissions
3. Run with verbose output: `bash -x ./installer/build-local.sh`

### Installation Failures

**Prerequisites not met:**
- Run `installer/scripts/check_prerequisites.sh`
- Install Docker and Docker Compose
- Ensure minimum system requirements

**Permission errors:**
- Run installer with administrator/sudo privileges
- Check file permissions on installation directory

**Port conflicts:**
- Check if ports 5432, 6379, 8001, 8501, 9020 are available
- Stop conflicting services
- Modify port configuration in docker-compose.yml

### Runtime Issues

**Services won't start:**
```bash
# Check Docker
docker info

# Check logs
docker compose logs -f

# Restart services
docker compose down
docker compose up -d
```

**Can't access web interface:**
```bash
# Verify services are running
docker compose ps

# Check Streamlit logs
docker compose logs streamlit

# Test connectivity
curl http://localhost:8501
```

## Security Considerations

### API Keys
- Never commit API keys to version control
- Use environment variables (`.env` file)
- Restrict .env file permissions: `chmod 600 .env`

### Network Security
- Application binds to localhost by default
- For remote access, configure reverse proxy (nginx/Apache)
- Use HTTPS for production deployments
- Consider firewall rules for exposed ports

### Data Security
- Database credentials are auto-generated during installation
- Regular backups recommended for `/var/lib/dis-verification-genai`
- PostgreSQL data is encrypted at rest if disk encryption is enabled

## Performance Tuning

### Resource Allocation

**Docker Compose limits:**
Edit `docker-compose.yml` to adjust:
```yaml
services:
  fastapi:
    mem_limit: 4g      # Increase if processing large documents
    cpu_count: 4        # Adjust based on available cores
```

### Ollama GPU Acceleration

If NVIDIA GPU is available:
```bash
# Install NVIDIA Docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Ollama will automatically use GPU
```

## Monitoring

### Health Checks

```bash
# Check all services
docker compose ps

# Check individual service health
curl http://localhost:9020/     # FastAPI
curl http://localhost:8501/     # Streamlit
curl http://localhost:11434/api/tags  # Ollama
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f fastapi
docker compose logs -f streamlit
docker compose logs -f postgres

# System service (Linux)
journalctl -u dis-verification-genai -f
```

### Resource Usage

```bash
# Docker stats
docker stats

# Disk usage
docker system df

# Database size
docker compose exec postgres du -sh /var/lib/postgresql/data
```

## Backup and Restore

### Backup

```bash
# Backup database
docker compose exec postgres pg_dump -U g3nA1-user rag_memory > backup_$(date +%Y%m%d).sql

# Backup vectors
docker compose exec chromadb tar czf - /chroma > chromadb_backup_$(date +%Y%m%d).tar.gz

# Backup configuration
cp .env .env.backup
```

### Restore

```bash
# Restore database
cat backup_20251114.sql | docker compose exec -T postgres psql -U g3nA1-user rag_memory

# Restore vectors
cat chromadb_backup_20251114.tar.gz | docker compose exec -T chromadb tar xzf - -C /
```

## Support

### For End Users
- Documentation: See INSTALL.md, README.md, QUICKSTART.md
- Issues: https://github.com/martinmanuel9/jitc_genai/issues
- Email: support@example.com

### For Developers
- Build issues: Check installer/README.md
- CI/CD issues: Check .github/workflows/build-installers.yml
- Contributing: See CONTRIBUTING.md (if exists)

## Appendix

### File Structure

```
jitc_genai/
├── VERSION                    # Current version number
├── CHANGELOG.md              # Release notes
├── QUICKSTART.md             # Quick start for users
├── INSTALL.md                # Detailed installation guide
├── README.md                 # User guide
├── .env.template             # Environment configuration template
├── docker-compose.yml        # Service orchestration
├── installer/
│   ├── README.md            # Installer development guide
│   ├── DEPLOYMENT_GUIDE.md  # This file
│   ├── metadata.json        # Installer metadata
│   ├── build-local.sh       # Local build script
│   ├── scripts/
│   │   ├── check_prerequisites.sh
│   │   ├── install-ollama.sh
│   │   ├── setup-env.sh
│   │   └── pull-ollama-models.sh
│   ├── windows/
│   │   ├── Product.wxs      # WiX configuration
│   │   └── scripts/
│   │       └── check_prerequisites.ps1
│   ├── linux/
│   │   └── DEBIAN/
│   │       ├── control      # DEB package metadata
│   │       ├── postinst     # Post-install script
│   │       ├── prerm        # Pre-removal script
│   │       └── postrm       # Post-removal script
│   └── macos/               # Generated during build
└── .github/
    └── workflows/
        └── build-installers.yml  # CI/CD pipeline
```

### Version History

See [CHANGELOG.md](../CHANGELOG.md) for detailed version history.
