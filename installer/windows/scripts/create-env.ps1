###############################################################################
# Create .env file from installer input
# Simple script to write .env content to file
###############################################################################

param(
    [string]$InstallDir = "$env:ProgramFiles\GenAI Research",
    [string]$EnvContent = ""
)

$ErrorActionPreference = "Continue"

# Log file for debugging - use TEMP so we can always write to it
$logFile = Join-Path $env:TEMP "dis-genai-env-creation.log"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        "[$timestamp] $Message" | Out-File -FilePath $logFile -Append -ErrorAction SilentlyContinue
    } catch {
        # Ignore log errors
    }
    Write-Host "[$timestamp] $Message" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  GenAI Research - .env File Creation" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

Write-Log "Starting .env file creation"
Write-Log "Install Directory: $InstallDir"
Write-Log "Content Length: $($EnvContent.Length) characters"

$envPath = Join-Path $InstallDir ".env"
Write-Log "Target .env path: $envPath"

try {
    # Create directory if it doesn't exist
    if (-not (Test-Path $InstallDir)) {
        Write-Log "Creating install directory: $InstallDir"
        New-Item -Path $InstallDir -ItemType Directory -Force | Out-Null
    }

    if ($EnvContent -and $EnvContent.Trim()) {
        Write-Log "Writing .env content to file..."

        # Write content to file
        $EnvContent | Out-File -FilePath $envPath -Encoding UTF8 -Force

        Write-Host ""
        Write-Host "SUCCESS: .env file created!" -ForegroundColor Green

        # Verify the file was created
        if (Test-Path $envPath) {
            $size = (Get-Item $envPath).Length
            Write-Log "Verified: File exists, size: $size bytes"

            # Show first few lines for confirmation
            Write-Host ""
            Write-Host "First few lines of .env file:" -ForegroundColor Yellow
            Get-Content $envPath -TotalCount 3 | ForEach-Object { Write-Host "  $_" }
            Write-Host "  ..." -ForegroundColor DarkGray
        } else {
            Write-Host "ERROR: File was not created!" -ForegroundColor Red
            Write-Log "ERROR: File was not created!"
        }
    } else {
        Write-Log "WARNING: No content provided (length: $($EnvContent.Length))"
        Write-Log "Checking for template..."

        $template = Join-Path $InstallDir ".env.template"
        if (Test-Path $template) {
            Write-Log "Copying from template: $template"
            Copy-Item $template $envPath -Force
            Write-Host "SUCCESS: .env file created from template" -ForegroundColor Green
        } else {
            Write-Host "ERROR: No content provided and no template found" -ForegroundColor Red
            Write-Log "ERROR: No content and no template found at $template"
        }
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Log "ERROR: $($_.Exception.Message)"
    Write-Log "Stack trace: $($_.ScriptStackTrace)"
}

Write-Host ""
Write-Log "Script completed. Log saved to: $logFile"
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

# Keep window open if running manually
if ($Host.Name -eq "ConsoleHost") {
    Write-Host "Press any key to continue..." -ForegroundColor Yellow
    $null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
