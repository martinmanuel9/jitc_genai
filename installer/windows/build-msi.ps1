###############################################################################
# Windows MSI Builder Script
# Builds the Windows installer package
###############################################################################

param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\.." | Select-Object -ExpandProperty Path),
    [string]$OutputDir = "$ProjectRoot\dist",
    [string]$Version = (Get-Content "$ProjectRoot\VERSION" -Raw).Trim()
)

$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host "         GenAI Research - Windows MSI Builder"
Write-Host "         Version: $Version"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

# Check for WiX Toolset
Write-Info "Checking for WiX Toolset..."
$wixPath = "${env:WIX}bin"
if (-not $env:WIX) {
    Write-ErrorMsg "WiX Toolset not found"
    Write-Host "Download and install from: https://wixtoolset.org/releases/"
    exit 1
}
Write-Success "WiX Toolset found: $wixPath"

$heatExe = Join-Path $wixPath "heat.exe"
$candleExe = Join-Path $wixPath "candle.exe"
$lightExe = Join-Path $wixPath "light.exe"

# Create build directory
$buildDir = "$ProjectRoot\build\windows"
$stagingDir = "$buildDir\staging"
if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
}
New-Item -ItemType Directory -Path $buildDir | Out-Null
New-Item -ItemType Directory -Path $stagingDir | Out-Null
Write-Info "Created build directory: $buildDir"

# Copy application files to staging
Write-Info "Copying application files to staging directory..."

# Required files
$requiredFiles = @(
    "docker-compose.yml",
    "Dockerfile.base",
    ".env.template",
    "VERSION",
    "CHANGELOG.md",
    "README.md",
    "INSTALL.md",
    "poetry.lock",
    "pyproject.toml",
    "run.sh"
)

# Optional files (copy if they exist)
$optionalFiles = @(
    ".env"
)

foreach ($file in $requiredFiles) {
    $sourcePath = Join-Path $ProjectRoot $file
    if (-not (Test-Path $sourcePath)) {
        Write-ErrorMsg "Missing required file: $file"
        exit 1
    }
    Copy-Item $sourcePath $stagingDir
}

# Copy optional files if they exist
foreach ($file in $optionalFiles) {
    $sourcePath = Join-Path $ProjectRoot $file
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath $stagingDir
        Write-Info "Copied optional file: $file"
    } else {
        Write-Host "[INFO] Optional file not found (will be created during install): $file" -ForegroundColor Yellow
    }
}

# Copy directories
Write-Info "Copying src directory..."
Copy-Item -Recurse "$ProjectRoot\src" $stagingDir

Write-Info "Copying scripts directory..."
Copy-Item -Recurse "$ProjectRoot\scripts" $stagingDir
Copy-Item -Recurse "$PSScriptRoot\scripts\*" "$stagingDir\scripts" -Force

# Copy LICENSE.rtf (required by WiX UI)
$licenseFile = "$PSScriptRoot\LICENSE.rtf"
if (-not (Test-Path $licenseFile)) {
    Write-ErrorMsg "LICENSE.rtf not found at: $licenseFile"
    Write-ErrorMsg "Please ensure installer/windows/LICENSE.rtf exists"
    exit 1
}
Copy-Item $licenseFile $buildDir

# Copy icon file (optional)
$iconFile = "$PSScriptRoot\app-icon.ico"
if (Test-Path $iconFile) {
    Copy-Item $iconFile $buildDir
    Write-Info "Icon file copied to build directory"
} else {
    Write-Warning "Icon file not found at: $iconFile"
    Write-Warning "Installer will use default icon."
}

Write-Success "All files copied to staging"

# Verify critical files
Write-Info "Verifying critical files..."
$criticalScripts = @(
    "scripts\setup-env.ps1",
    "scripts\post-install.ps1",
    "scripts\check_prerequisites.ps1",
    "scripts\create-env-from-input.ps1"
)

foreach ($script in $criticalScripts) {
    $scriptPath = Join-Path $stagingDir $script
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "Missing critical script: $script"
        exit 1
    }
}
Write-Success "All critical files verified"

# Use heat.exe to harvest the staging directory
Write-Info "Harvesting files with heat.exe..."
$fragmentFile = "$buildDir\FilesFragment.wxs"

& $heatExe dir "$stagingDir" `
    -cg ApplicationFiles `
    -gg `
    -sfrag `
    -srd `
    -dr INSTALLFOLDER `
    -var "var.StagingDir" `
    -out $fragmentFile

if ($LASTEXITCODE -ne 0) {
    Write-ErrorMsg "heat.exe failed"
    exit 1
}
Write-Success "Files harvested successfully"

# Update Product.wxs with version
$productWxs = "$PSScriptRoot\Product.wxs"
$productWxsContent = Get-Content $productWxs -Raw
$productWxsContent = $productWxsContent -replace 'VERSION_PLACEHOLDER', $Version
$productWxsBuild = "$buildDir\Product.wxs"
Set-Content -Path $productWxsBuild -Value $productWxsContent

# Copy CustomUI.wxs to build directory
$customUIWxs = "$PSScriptRoot\CustomUI.wxs"
if (Test-Path $customUIWxs) {
    Copy-Item $customUIWxs $buildDir
    Write-Info "CustomUI.wxs copied to build directory"
} else {
    Write-ErrorMsg "CustomUI.wxs not found at: $customUIWxs"
    exit 1
}

# Compile .wxs files to .wixobj
Write-Info "Compiling WiX sources..."
$customUIBuild = "$buildDir\CustomUI.wxs"
$wixFiles = @($productWxsBuild, $fragmentFile, $customUIBuild)
Write-Info "Files to compile: $($wixFiles.Count)"
foreach ($f in $wixFiles) {
    Write-Info "  - $f (exists: $(Test-Path $f))"
}
$wixObjs = @()

foreach ($wxsFile in $wixFiles) {
    Write-Host ""
    Write-Info "==== Compiling: $wxsFile ===="
    $wixObj = $wxsFile -replace '\.wxs$', '.wixobj'
    $wixObjs += $wixObj

    Write-Info "Command: candle.exe $wxsFile -out $wixObj"
    & $candleExe $wxsFile `
        -dStagingDir="$stagingDir" `
        -dVersion=$Version `
        -out $wixObj `
        -arch x64 `
        -ext WixUIExtension `
        -ext WixUtilExtension

    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "candle.exe failed for $wxsFile with exit code: $LASTEXITCODE"
        exit 1
    }
    Write-Success "Successfully compiled: $wxsFile -> $wixObj"
}
Write-Success "WiX sources compiled"

# Link .wixobj files to create .msi
Write-Info "Linking MSI package..."
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$msiFile = "$OutputDir\dis-verification-genai-$Version.msi"

& $lightExe $wixObjs `
    -out $msiFile `
    -ext WixUIExtension `
    -ext WixUtilExtension `
    -cultures:en-US

if ($LASTEXITCODE -ne 0) {
    Write-ErrorMsg "light.exe failed"
    exit 1
}

Write-Host ""
Write-Success "MSI package built successfully!"
Write-Host ""
Write-Info "Output: $msiFile"
Write-Host ""
Write-Info "Package size: $([math]::Round((Get-Item $msiFile).Length / 1MB, 2)) MB"
Write-Host ""
