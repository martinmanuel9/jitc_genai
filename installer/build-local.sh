#!/bin/bash
###############################################################################
# Local Installer Build Script
# Builds installers for testing before pushing to GitHub
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(cat "$PROJECT_ROOT/VERSION")

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "         GenAI Research - Local Build Script"
echo "         Version: $VERSION"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Parse arguments
BUILD_TARGET="${1:-all}"
BUILD_ARCH="${2:-$(uname -m)}"

# Normalize architecture names
normalize_arch() {
    case "$1" in
        x86_64|amd64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            echo "$1"
            ;;
    esac
}

normalize_rpm_arch() {
    case "$1" in
        amd64|x86_64)
            echo "x86_64"
            ;;
        arm64|aarch64)
            echo "aarch64"
            ;;
        *)
            echo "$1"
            ;;
    esac
}

DEB_ARCH=$(normalize_arch "$BUILD_ARCH")
RPM_ARCH=$(normalize_rpm_arch "$BUILD_ARCH")

build_linux_deb() {
    local TARGET_ARCH="${1:-$DEB_ARCH}"
    print_info "Building Linux DEB package for $TARGET_ARCH..."

    local PKG_DIR="genai-research_${VERSION}_${TARGET_ARCH}"
    local BUILD_DIR="$PROJECT_ROOT/build/deb-${TARGET_ARCH}"

    # Clean previous build
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"

    # Create package structure
    mkdir -p "$BUILD_DIR/$PKG_DIR/opt/jitc_genai"
    mkdir -p "$BUILD_DIR/$PKG_DIR/DEBIAN"

    # Copy application files
    print_info "Copying application files..."

    # Verify source files exist before copying
    for file in src scripts docker-compose.yml .env.template VERSION CHANGELOG.md README.md INSTALL.md; do
        if [ ! -e "$PROJECT_ROOT/$file" ]; then
            print_error "Missing required file/directory: $file"
            exit 1
        fi
    done

    # Verify critical scripts exist
    for script in setup-env.sh install-ollama.sh pull-ollama-models.sh verify-installation.sh; do
        if [ ! -f "$PROJECT_ROOT/scripts/$script" ]; then
            print_error "Missing required script: scripts/$script"
            exit 1
        fi
    done

    # Copy with verification
    cp -r "$PROJECT_ROOT/src" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy src"; exit 1; }
    cp -r "$PROJECT_ROOT/scripts" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy scripts"; exit 1; }
    cp "$PROJECT_ROOT/docker-compose.yml" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy docker-compose.yml"; exit 1; }
    cp "$PROJECT_ROOT/Dockerfile.base" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy Dockerfile.base"; exit 1; }
    cp "$PROJECT_ROOT/pyproject.toml" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy pyproject.toml"; exit 1; }
    cp "$PROJECT_ROOT/poetry.lock" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy poetry.lock"; exit 1; }
    cp "$PROJECT_ROOT/run" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy run"; exit 1; }
    chmod +x "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/run"
    cp "$PROJECT_ROOT/.env.template" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/.env.template" || { print_error "Failed to copy .env.template"; exit 1; }
    cp "$PROJECT_ROOT/.env.template" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/.env" || { print_error "Failed to copy .env"; exit 1; }
    cp "$PROJECT_ROOT/VERSION" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy VERSION"; exit 1; }
    cp "$PROJECT_ROOT/CHANGELOG.md" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy CHANGELOG.md"; exit 1; }
    cp "$PROJECT_ROOT/README.md" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy README.md"; exit 1; }
    cp "$PROJECT_ROOT/INSTALL.md" "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/" || { print_error "Failed to copy INSTALL.md"; exit 1; }

    # Verify all files were copied
    print_info "Verifying copied files..."
    for file in src scripts docker-compose.yml Dockerfile.base pyproject.toml poetry.lock run .env.template .env VERSION CHANGELOG.md README.md INSTALL.md; do
        if [ ! -e "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/$file" ]; then
            print_error "Verification failed: $file was not copied"
            exit 1
        fi
    done
    print_success "All application files copied and verified"

    # Copy DEBIAN control files
    cp "$SCRIPT_DIR/linux/DEBIAN/"* "$BUILD_DIR/$PKG_DIR/DEBIAN/"

    # Update version and architecture in control file
    sed -i "s/VERSION_PLACEHOLDER/$VERSION/g" "$BUILD_DIR/$PKG_DIR/DEBIAN/control"
    sed -i "s/Architecture: amd64/Architecture: $TARGET_ARCH/g" "$BUILD_DIR/$PKG_DIR/DEBIAN/control"

    # Set permissions
    chmod 755 "$BUILD_DIR/$PKG_DIR/DEBIAN/postinst"
    chmod 755 "$BUILD_DIR/$PKG_DIR/DEBIAN/prerm"
    chmod 755 "$BUILD_DIR/$PKG_DIR/DEBIAN/postrm"
    chmod +x "$BUILD_DIR/$PKG_DIR/opt/jitc_genai/scripts/"*.sh

    # Build DEB package
    print_info "Building DEB package..."
    cd "$BUILD_DIR"
    dpkg-deb --build "$PKG_DIR"

    # Move to output directory
    mkdir -p "$PROJECT_ROOT/dist"
    mv "$BUILD_DIR/${PKG_DIR}.deb" "$PROJECT_ROOT/dist/"

    print_success "DEB package built: dist/${PKG_DIR}.deb"
}

build_linux_rpm() {
    local TARGET_ARCH="${1:-$RPM_ARCH}"
    print_info "Building Linux RPM package for $TARGET_ARCH..."

    if ! command -v rpmbuild &> /dev/null; then
        print_error "rpmbuild not found. Install with: sudo apt-get install rpm"
        return 1
    fi

    local SPEC_FILE="$SCRIPT_DIR/linux/genai-research.spec"

    # Create RPM build directories
    mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

    # Create spec file
    cat > "$SPEC_FILE" <<EOF
Name:           genai-research
Version:        $VERSION
Release:        1%{?dist}
Summary:        AI-powered research and verification system
License:        Proprietary
URL:            https://github.com/martinmanuel9/jitc_genai
Requires:       docker >= 24.0.0
BuildArch:      $TARGET_ARCH

%description
GenAI Research provides comprehensive AI-powered research and
verification capabilities using advanced AI models. Features include:
- Multi-agent test plan generation with Actor-Critic system
- RAG-enhanced document analysis with citation tracking
- Test card creation with Word export
- Support for cloud LLMs (OpenAI) and local models (Ollama)
- US-based model compliance (Meta, Microsoft, Snowflake)
- Complete on-premises deployment option

%prep
# No prep needed - files come from staging

%build
# No build needed - Python/Docker application

%install
mkdir -p %{buildroot}/opt/jitc_genai
cp -r $PROJECT_ROOT/src %{buildroot}/opt/jitc_genai/
cp -r $PROJECT_ROOT/scripts %{buildroot}/opt/jitc_genai/
cp $PROJECT_ROOT/docker-compose.yml %{buildroot}/opt/jitc_genai/
cp $PROJECT_ROOT/.env.template %{buildroot}/opt/jitc_genai/.env
cp $PROJECT_ROOT/VERSION %{buildroot}/opt/jitc_genai/
cp $PROJECT_ROOT/CHANGELOG.md %{buildroot}/opt/jitc_genai/
cp $PROJECT_ROOT/README.md %{buildroot}/opt/jitc_genai/
cp $PROJECT_ROOT/INSTALL.md %{buildroot}/opt/jitc_genai/

%files
%defattr(-,root,root,-)
/opt/jitc_genai

%post
# Run post-installation script
if [ -f /opt/jitc_genai/scripts/rpm-postinst.sh ]; then
    bash /opt/jitc_genai/scripts/rpm-postinst.sh
fi

%preun
# Stop and disable service before uninstall
if systemctl is-active --quiet jitc_genai; then
    systemctl stop jitc_genai
fi
if systemctl is-enabled --quiet jitc_genai; then
    systemctl disable jitc_genai
fi

%postun
# Remove systemd service file on purge
if [ \$1 -eq 0 ]; then
    rm -f /etc/systemd/system/jitc_genai.service
    systemctl daemon-reload
fi

%changelog
* $(date +'%a %b %d %Y') Developer <dev@example.com> - $VERSION-1
- Release $VERSION
EOF

    # Copy RPM postinst script to project scripts (will be included in package)
    cp "$SCRIPT_DIR/linux/rpm-postinst.sh" "$PROJECT_ROOT/scripts/" 2>/dev/null || true

    # Create source tarball
    print_info "Creating source tarball..."
    cd "$PROJECT_ROOT"
    tar czf ~/rpmbuild/SOURCES/genai-research-$VERSION.tar.gz \
        --exclude='.git' \
        --exclude='build' \
        --exclude='dist' \
        --exclude='*.pyc' \
        src scripts docker-compose.yml .env.template VERSION CHANGELOG.md README.md

    # Build RPM
    print_info "Building RPM package for $TARGET_ARCH..."
    rpmbuild -ba "$SPEC_FILE" --target "$TARGET_ARCH"

    # Copy to dist
    mkdir -p "$PROJECT_ROOT/dist"
    cp ~/rpmbuild/RPMS/$TARGET_ARCH/genai-research-$VERSION-1.*.$TARGET_ARCH.rpm "$PROJECT_ROOT/dist/"

    print_success "RPM package built: dist/genai-research-$VERSION-1.*.$TARGET_ARCH.rpm"
}

build_macos_dmg() {
    print_info "Building macOS DMG..."

    if [[ "$(uname -s)" != "Darwin" ]]; then
        print_warning "macOS builds must be done on macOS"
        return 1
    fi

    # Detect macOS architecture
    local MACOS_ARCH=$(uname -m)
    case "$MACOS_ARCH" in
        x86_64)
            MACOS_ARCH="x86_64"
            ;;
        arm64)
            MACOS_ARCH="arm64"
            ;;
    esac

    local APP_NAME="GenAI Research"
    local DMG_NAME="genai-research-$VERSION-$MACOS_ARCH.dmg"
    local BUILD_DIR="$PROJECT_ROOT/build/macos-$MACOS_ARCH"

    # Clean previous build
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"

    # Create app bundle
    print_info "Creating app bundle..."
    mkdir -p "$BUILD_DIR/$APP_NAME.app/Contents/MacOS"
    mkdir -p "$BUILD_DIR/$APP_NAME.app/Contents/Resources"

    # Copy application files
    cp -r "$PROJECT_ROOT/src" "$BUILD_DIR/$APP_NAME.app/Contents/Resources/"
    cp -r "$PROJECT_ROOT/scripts" "$BUILD_DIR/$APP_NAME.app/Contents/Resources/"
    cp "$PROJECT_ROOT/docker-compose.yml" "$BUILD_DIR/$APP_NAME.app/Contents/Resources/"
    cp "$PROJECT_ROOT/.env.template" "$BUILD_DIR/$APP_NAME.app/Contents/Resources/.env"
    cp "$PROJECT_ROOT/VERSION" "$BUILD_DIR/$APP_NAME.app/Contents/Resources/"
    cp "$PROJECT_ROOT/CHANGELOG.md" "$BUILD_DIR/$APP_NAME.app/Contents/Resources/"
    cp "$PROJECT_ROOT/README.md" "$BUILD_DIR/$APP_NAME.app/Contents/Resources/"

    # Create Info.plist with architecture info
    cat > "$BUILD_DIR/$APP_NAME.app/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>GenAI Research</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>LSArchitecturePriority</key>
    <array>
        <string>$MACOS_ARCH</string>
    </array>
</dict>
</plist>
EOF

    # Create launcher script with setup
    cat > "$BUILD_DIR/$APP_NAME.app/Contents/MacOS/launcher" <<'EOF'
#!/bin/bash
RESOURCES_DIR="$(dirname "$0")/../Resources"
cd "$RESOURCES_DIR"

# Run setup on first launch if .env doesn't exist
if [ ! -f "$RESOURCES_DIR/.env" ] || [ ! -s "$RESOURCES_DIR/.env" ]; then
    osascript -e 'tell app "Terminal" to do script "cd '"$RESOURCES_DIR"' && ./scripts/setup-env.sh"'
    exit 0
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    osascript -e 'display dialog "Docker Desktop is not running. Please start Docker Desktop first." buttons {"OK"} default button "OK"'
    open -a "Docker"
    exit 1
fi

# Start services
docker compose up -d

# Wait for services
sleep 5

# Open web interface
open http://localhost:8501
EOF
    chmod +x "$BUILD_DIR/$APP_NAME.app/Contents/MacOS/launcher"

    # Create setup script launcher
    cat > "$BUILD_DIR/$APP_NAME.app/Contents/MacOS/setup" <<'EOF'
#!/bin/bash
RESOURCES_DIR="$(dirname "$0")/../Resources"
cd "$RESOURCES_DIR"
osascript -e 'tell app "Terminal" to do script "cd '"$RESOURCES_DIR"' && ./scripts/setup-env.sh && exit"'
EOF
    chmod +x "$BUILD_DIR/$APP_NAME.app/Contents/MacOS/setup"

    # Create DMG
    print_info "Creating DMG..."
    mkdir -p "$PROJECT_ROOT/dist"
    hdiutil create -volname "$APP_NAME" -srcfolder "$BUILD_DIR" -ov -format UDZO "$PROJECT_ROOT/dist/$DMG_NAME"

    print_success "DMG created: dist/$DMG_NAME"
}

# Main build logic
case "$BUILD_TARGET" in
    deb)
        build_linux_deb "$DEB_ARCH"
        ;;
    rpm)
        build_linux_rpm "$RPM_ARCH"
        ;;
    dmg)
        build_macos_dmg
        ;;
    linux)
        build_linux_deb "$DEB_ARCH"
        build_linux_rpm "$RPM_ARCH"
        ;;
    all)
        print_info "Building all packages for current architecture ($BUILD_ARCH)..."
        build_linux_deb "$DEB_ARCH" || true
        build_linux_rpm "$RPM_ARCH" || true
        if [[ "$(uname -s)" == "Darwin" ]]; then
            build_macos_dmg || true
        fi
        ;;
    all-arch)
        print_info "Building all packages for all architectures..."
        build_linux_deb "amd64" || true
        build_linux_deb "arm64" || true
        build_linux_rpm "x86_64" || true
        build_linux_rpm "aarch64" || true
        if [[ "$(uname -s)" == "Darwin" ]]; then
            build_macos_dmg || true
        fi
        ;;
    *)
        print_error "Invalid build target: $BUILD_TARGET"
        echo ""
        echo "Usage: $0 [deb|rpm|dmg|linux|all|all-arch] [architecture]"
        echo ""
        echo "Targets:"
        echo "  deb       - Build Debian/Ubuntu package"
        echo "  rpm       - Build RHEL/CentOS/Fedora package"
        echo "  dmg       - Build macOS package (macOS only)"
        echo "  linux     - Build both DEB and RPM"
        echo "  all       - Build all available packages for current arch [default]"
        echo "  all-arch  - Build all packages for both amd64 and arm64"
        echo ""
        echo "Architectures (optional, defaults to current system):"
        echo "  amd64/x86_64   - Intel/AMD 64-bit"
        echo "  arm64/aarch64  - ARM 64-bit (AWS Graviton, Apple Silicon, etc.)"
        echo ""
        echo "Examples:"
        echo "  $0 deb           # Build DEB for current architecture"
        echo "  $0 deb arm64     # Build DEB for ARM64"
        echo "  $0 all-arch      # Build all packages for all architectures"
        exit 1
        ;;
esac

echo ""
print_success "Build completed!"
echo ""
if [ -d "$PROJECT_ROOT/dist" ]; then
    print_info "Built packages:"
    ls -lh "$PROJECT_ROOT/dist/"
fi
echo ""
