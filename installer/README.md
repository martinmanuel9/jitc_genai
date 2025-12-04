# Installer Development Guide

This directory contains the configuration and scripts for building cross-platform installers for GenAI Research.

## Table of Contents
- [Overview](#overview)
- [Installer Formats](#installer-formats)
- [Building Installers](#building-installers)
- [CI/CD Pipeline](#cicd-pipeline)
- [Version Management](#version-management)
- [Testing Installers](#testing-installers)
- [Troubleshooting](#troubleshooting)

## Overview

The installer system supports three major platforms:
- **Windows:** MSI package using WiX Toolset
- **Linux:** DEB (Debian/Ubuntu) and RPM (RHEL/CentOS/Fedora) packages
- **macOS:** DMG disk image with app bundle

All installers include:
- Prerequisites checking
- Docker dependency verification
- Automatic service configuration
- Post-install setup wizards
- Version tracking
- Uninstallation support

## Installer Formats

### Windows MSI (WiX)

**Location:** `windows/Product.wxs`

**Features:**
- Windows Installer XML (WiX) configuration
- Prerequisites check via PowerShell
- Start Menu and Desktop shortcuts
- Registry entries for uninstallation
- Service auto-start configuration
- Upgrade support with automatic uninstall of old versions

**Build Requirements:**
- WiX Toolset 3.11+
- .NET Framework 3.5+
- Windows 10+ for building

### Linux DEB

**Location:** `linux/DEBIAN/`

**Features:**
- Debian package format
- systemd service integration
- Post-install configuration scripts
- Dependency checking (Docker, Docker Compose)
- Service user creation
- Data preservation on upgrade

**Build Requirements:**
- `dpkg-dev`
- `build-essential`
- Ubuntu 20.04+ or Debian 11+

### Linux RPM

**Location:** `linux/*.spec` (generated)

**Features:**
- RPM package format
- systemd service integration
- Post-install configuration scripts
- Dependency checking

**Build Requirements:**
- `rpmbuild`
- RHEL 8+, CentOS 8+, or Fedora 35+

### macOS DMG

**Location:** `macos/` (generated)

**Features:**
- DMG disk image
- Application bundle (.app)
- Drag-to-Applications installation
- Launcher script for Docker Compose

**Build Requirements:**
- macOS 11+ (Big Sur or later)
- Xcode Command Line Tools

## Building Installers

### Local Development Build

Use the `build-local.sh` script to build installers on your development machine:

```bash
# Build all available packages
./installer/build-local.sh all

# Build specific package
./installer/build-local.sh deb      # Debian/Ubuntu package
./installer/build-local.sh rpm      # RHEL/CentOS/Fedora package
./installer/build-local.sh dmg      # macOS package (macOS only)
./installer/build-local.sh linux    # Both DEB and RPM
```

**Output:** Built packages will be in `dist/` directory.

### Prerequisites for Local Build

**Linux (for DEB/RPM):**
```bash
# Install build tools
sudo apt-get install dpkg-dev build-essential rpm

# Make script executable
chmod +x installer/build-local.sh
```

**macOS (for DMG):**
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Make script executable
chmod +x installer/build-local.sh
```

**Windows (for MSI):**
```powershell
# Install WiX Toolset
choco install wixtoolset

# Add WiX to PATH
$env:PATH += ";C:\Program Files (x86)\WiX Toolset v3.11\bin"
```

### Manual Build Process

#### Building DEB Package Manually

```bash
# Set version
VERSION=$(cat VERSION)
PKG_DIR="dis-verification-genai_${VERSION}_amd64"

# Create directory structure
mkdir -p "$PKG_DIR/opt/dis-verification-genai"
mkdir -p "$PKG_DIR/DEBIAN"

# Copy files
cp -r src "$PKG_DIR/opt/dis-verification-genai/"
cp -r scripts "$PKG_DIR/opt/dis-verification-genai/"
cp docker-compose.yml "$PKG_DIR/opt/dis-verification-genai/"
cp .env.template "$PKG_DIR/opt/dis-verification-genai/.env"
cp VERSION CHANGELOG.md README.md "$PKG_DIR/opt/dis-verification-genai/"

# Copy DEBIAN control files
cp installer/linux/DEBIAN/* "$PKG_DIR/DEBIAN/"

# Update version
sed -i "s/VERSION_PLACEHOLDER/$VERSION/g" "$PKG_DIR/DEBIAN/control"

# Set permissions
chmod 755 "$PKG_DIR/DEBIAN/"*

# Build package
dpkg-deb --build "$PKG_DIR"
```

#### Building WiX MSI Manually

```powershell
# Navigate to Windows installer directory
cd installer\windows

# Update version in Product.wxs
$VERSION = Get-Content ..\..\VERSION
(Get-Content Product.wxs) -replace 'VERSION_PLACEHOLDER', $VERSION | Set-Content Product.wxs

# Compile
candle.exe Product.wxs -ext WixUIExtension -ext WixUtilExtension

# Link
light.exe Product.wixobj -ext WixUIExtension -ext WixUtilExtension -out ..\..\dist\dis-verification-genai-$VERSION.msi
```

## CI/CD Pipeline

### GitHub Actions Workflow

**Location:** `.github/workflows/build-installers.yml`

**Trigger Methods:**

1. **Git Tag Push:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Manual Workflow Dispatch:**
   - Go to GitHub Actions tab
   - Select "Build Installers" workflow
   - Click "Run workflow"
   - Enter version number

**Workflow Steps:**

1. **Prepare Release**
   - Determines version from tag or input
   - Updates VERSION file
   - Creates GitHub Release

2. **Build Windows Installer**
   - Runs on Windows runner
   - Installs WiX Toolset
   - Builds MSI package
   - Uploads to GitHub Release

3. **Build Linux DEB**
   - Runs on Ubuntu runner
   - Creates DEB package structure
   - Builds package with dpkg-deb
   - Uploads to GitHub Release

4. **Build Linux RPM**
   - Runs on Ubuntu runner
   - Creates RPM spec file
   - Builds package with rpmbuild
   - Uploads to GitHub Release

5. **Build macOS DMG**
   - Runs on macOS runner
   - Creates app bundle
   - Generates DMG image
   - Uploads to GitHub Release

6. **Generate Checksums**
   - Creates SHA256 checksums
   - Uploads checksum file

### Release Assets

After successful build, the following assets are available:

- `dis-verification-genai-{version}.msi` - Windows installer
- `dis-verification-genai_{version}_amd64.deb` - Debian/Ubuntu package
- `dis-verification-genai-{version}.x86_64.rpm` - RHEL/CentOS/Fedora package
- `dis-verification-genai-{version}.dmg` - macOS disk image
- `checksums-sha256.txt` - SHA256 checksums for verification

## Version Management

### Semantic Versioning

We follow [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR:** Incompatible API changes
- **MINOR:** New functionality, backwards compatible
- **PATCH:** Backwards compatible bug fixes

**Format:** `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)

### Version Files

- **VERSION:** Contains current version number (single line)
- **CHANGELOG.md:** Human-readable changelog following [Keep a Changelog](https://keepachangelog.com/)
- **metadata.json:** Installer metadata and configuration

### Updating Version

1. **Update VERSION file:**
   ```bash
   echo "1.1.0" > VERSION
   ```

2. **Update CHANGELOG.md:**
   ```markdown
   ## [1.1.0] - 2025-11-15

   ### Added
   - New feature description

   ### Fixed
   - Bug fix description
   ```

3. **Commit and tag:**
   ```bash
   git add VERSION CHANGELOG.md
   git commit -m "Bump version to 1.1.0"
   git tag v1.1.0
   git push origin main v1.1.0
   ```

4. **GitHub Actions will automatically build installers**

## Testing Installers

### Pre-Release Testing

Before pushing a release tag, test installers locally:

1. **Build local installers:**
   ```bash
   ./installer/build-local.sh all
   ```

2. **Test on clean VM or Docker container:**
   ```bash
   # For DEB
   docker run -it --rm -v $(pwd)/dist:/packages ubuntu:22.04
   apt-get update && apt-get install -y /packages/dis-verification-genai_*.deb

   # For RPM
   docker run -it --rm -v $(pwd)/dist:/packages fedora:latest
   dnf install -y /packages/dis-verification-genai-*.rpm
   ```

3. **Verify installation:**
   - Check files are in correct locations
   - Verify systemd service is created
   - Test service start/stop
   - Check web interface accessibility
   - Test uninstallation

### Automated Testing (Future)

Planned additions:
- Integration tests for installers
- VM-based installation tests
- Upgrade path testing
- Uninstall verification tests

## Troubleshooting

### Common Build Issues

**Issue:** WiX Toolset not found
```
Solution: Install WiX and add to PATH
choco install wixtoolset
```

**Issue:** dpkg-deb: error: failed to make tmpfile (control)
```
Solution: Check DEBIAN control file permissions
chmod 755 installer/linux/DEBIAN/*
```

**Issue:** rpmbuild: command not found
```
Solution: Install RPM build tools
sudo apt-get install rpm
```

**Issue:** hdiutil: create failed - Resource busy
```
Solution: Unmount existing DMG
hdiutil detach /Volumes/DIS\ Verification\ GenAI
```

### GitHub Actions Failures

**Windows Build Fails:**
- Check WiX syntax in Product.wxs
- Verify all source files exist
- Check VERSION file format

**Linux Build Fails:**
- Verify DEBIAN/control file format
- Check postinst/prerm/postrm scripts
- Ensure all dependencies are listed

**macOS Build Fails:**
- Check Info.plist XML syntax
- Verify app bundle structure
- Ensure launcher script is executable

### Debugging Tips

1. **Enable verbose logging:**
   ```yaml
   # In GitHub Actions workflow
   - name: Build with verbose output
     run: dpkg-deb --verbose --build ...
   ```

2. **Test scripts independently:**
   ```bash
   bash -x installer/scripts/check_prerequisites.sh
   ```

3. **Validate package structure:**
   ```bash
   # DEB package
   dpkg-deb --contents dist/dis-verification-genai_*.deb
   dpkg-deb --info dist/dis-verification-genai_*.deb

   # RPM package
   rpm -qpl dist/dis-verification-genai-*.rpm
   rpm -qpi dist/dis-verification-genai-*.rpm
   ```

## Best Practices

1. **Version Consistency:** Always update VERSION file before building
2. **Testing:** Test installers on clean systems before release
3. **Changelog:** Keep CHANGELOG.md up-to-date with every change
4. **Dependencies:** Clearly document all prerequisites
5. **Backward Compatibility:** Test upgrades from previous versions
6. **Clean Uninstall:** Ensure uninstaller removes all files properly
7. **Data Preservation:** Never delete user data without confirmation

## Contributing

When adding new installer features:

1. Update relevant configuration files
2. Test on target platform
3. Update this documentation
4. Add tests if applicable
5. Update CHANGELOG.md

## Resources

- [WiX Toolset Documentation](https://wixtoolset.org/documentation/)
- [Debian Packaging Guide](https://www.debian.org/doc/manuals/maint-guide/)
- [RPM Packaging Guide](https://rpm-packaging-guide.github.io/)
- [macOS Bundle Programming Guide](https://developer.apple.com/library/archive/documentation/CoreFoundation/Conceptual/CFBundles/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
