# Viewing Installation Progress Output

## How It Works

The Windows installer now captures ALL output from the setup scripts and displays it in the MSI log viewer during installation.

### What Changed

**Before**: Used `WixQuietExec` - no output captured ❌

**After**: Uses `CAQuietExec` - all stdout/stderr captured and written to MSI log ✅

## How Users See The Output

### During Installation

When the installer reaches the "Configuring system and downloading models..." step:

1. **Progress dialog appears** showing:
   ```
   Installing GenAI Research

   Status: Configuring system and downloading models (this may take 10-20 minutes)...

   [Progress bar]
   ```

2. **User clicks small arrow/button** at bottom of dialog (usually says "Show log" or has a down arrow icon)

3. **Log pane expands** showing real-time output:
   ```
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: STEP 1/5: Environment Configuration
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: .env file verified successfully
   CAQuietExec:  CustomAction: .env file contains 45 lines of configuration
   CAQuietExec:  CustomAction: Step 1/5 Complete
   CAQuietExec:
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: STEP 2/5: Docker Verification
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: Docker is running
   CAQuietExec:  CustomAction: Step 2/5 Complete
   CAQuietExec:
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: STEP 3/5: System Hardware Detection
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: GPU detected: NVIDIA GeForce RTX 3080
   CAQuietExec:  CustomAction: System RAM: 32GB
   CAQuietExec:  CustomAction: Recommended model: llama3.1:8b
   CAQuietExec:  CustomAction: Step 3/5 Complete
   CAQuietExec:
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: STEP 4/5: AI Model Download
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: Downloading AI models (this may take 5-10 minutes)...
   CAQuietExec:  CustomAction: Step 4a: Pulling embedding model (required): snowflake-arctic-embed2
   CAQuietExec:  pulling manifest
   CAQuietExec:  pulling 2b0e7e5b0 100% ▕████████████████▏ 1.3 GB
   CAQuietExec:  verifying sha256 digest
   CAQuietExec:  writing manifest
   CAQuietExec:  success
   CAQuietExec:  CustomAction: Embedding model downloaded successfully
   CAQuietExec:
   CAQuietExec:  CustomAction: Step 4b: Pulling LLM model: llama3.1:8b
   CAQuietExec:  pulling manifest
   CAQuietExec:  pulling 8eeb52df 100% ▕████████████████▏ 4.7 GB
   CAQuietExec:  verifying sha256 digest
   CAQuietExec:  writing manifest
   CAQuietExec:  success
   CAQuietExec:  CustomAction: Model downloaded successfully: llama3.1:8b
   CAQuietExec:  CustomAction: Step 4/5 Complete
   CAQuietExec:
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: STEP 5/5: Building Docker Containers
   CAQuietExec:  CustomAction: ==========================================
   CAQuietExec:  CustomAction: Building base dependencies (this may take 5-10 minutes)...
   CAQuietExec:  CustomAction: Running: docker compose build base-poetry-deps
   CAQuietExec:  [+] Building 315.2s (12/12) FINISHED
   CAQuietExec:   => [internal] load build definition from Dockerfile.base
   CAQuietExec:   => => transferring dockerfile: 1.2kB
   CAQuietExec:   => [internal] load metadata for docker.io/library/python:3.11
   CAQuietExec:   => [1/7] FROM docker.io/library/python:3.11@sha256:abc123
   CAQuietExec:   => [2/7] WORKDIR /app
   CAQuietExec:   => [3/7] RUN pip install poetry==1.8.2
   CAQuietExec:   => [4/7] COPY pyproject.toml poetry.lock ./
   CAQuietExec:   => [5/7] RUN poetry install --no-root
   CAQuietExec:   => exporting to image
   CAQuietExec:  CustomAction: Base dependencies built successfully
   ...
   ```

All output prefixed with `CAQuietExec:` is from the custom action scripts!

### Important Notes

**CAQuietExec Output Format**:
- Every line from the PowerShell script appears prefixed with `CAQuietExec:`
- `Write-Host` output from PowerShell → Shows in log
- `ollama pull` progress → Shows in log
- `docker compose build` output → Shows in log
- Everything is captured in real-time!

**Log Viewer Features**:
- ✅ Auto-scrolls to show latest output
- ✅ User can scroll up/down to review
- ✅ Shows all stdout and stderr
- ✅ Updates in real-time as scripts run

## For Developers: Ensuring Output is Captured

### In PowerShell Scripts

```powershell
# ✅ GOOD - Will appear in log
Write-Host "CustomAction: This message will be visible"

# ✅ GOOD - External command output captured
ollama pull llama3.1:8b  # All output visible
docker compose build     # All output visible

# ❌ BAD - Will NOT appear
Write-Verbose "Hidden"     # Not captured
Write-Debug "Hidden"       # Not captured
# Internal PowerShell operations without output
```

### Custom Action Configuration

```xml
<!-- ✅ CORRECT - Captures output -->
<CustomAction Id="RunSetupScript"
              BinaryKey="WixCA"
              DllEntry="CAQuietExec"    <!-- Use CAQuietExec, not WixQuietExec -->
              Execute="deferred"
              Return="ignore"
              Impersonate="yes" />

<!-- ❌ WRONG - No output -->
<CustomAction Id="BadExample"
              BinaryKey="WixCA"
              DllEntry="WixQuietExec"   <!-- WixQuietExec = silent -->
              Execute="deferred" />
```

## Testing Installation with Verbose Logging

To generate a full log file for debugging:

```cmd
msiexec /i dis-verification-genai-1.0.13.msi /L*V install.log
```

Then open `install.log` and search for `CAQuietExec:` to see all script output.

## User Experience

### What Users See

1. **Installer progress dialog** with status message
2. **Small "Show log" button/arrow** at bottom
3. **Click it** to expand log pane
4. **Scrolling text output** showing all setup steps in real-time
5. **Can minimize/maximize** log pane as needed

### Benefits

✅ **Transparency**: Users see exactly what's happening
✅ **Progress tracking**: Can see which step is running
✅ **Error visibility**: If something fails, error messages appear immediately
✅ **Confidence**: Users know the installer is working, not frozen
✅ **Debugging**: If issues occur, users can copy log text

## Comparison: Before vs After

### Before (WixQuietExec)
```
[Installing GenAI Research]
[Progress bar]
Status: Configuring system...

<User sees nothing, waits 15 minutes, no idea what's happening>
```

### After (CAQuietExec)
```
[Installing GenAI Research]
[Progress bar]
Status: Configuring system...
[Show log ▼]

<Click "Show log">

CAQuietExec: CustomAction: STEP 3/5: System Hardware Detection
CAQuietExec: CustomAction: GPU detected: NVIDIA RTX 3080
CAQuietExec: CustomAction: Step 4/5: AI Model Download
CAQuietExec: pulling manifest
CAQuietExec: pulling 8eeb52df 45% ▕████████        ▏ 2.1/4.7 GB
<User can see download progress!>
```

## Summary

With `CAQuietExec`, users get a **professional installer experience** with:
- Real-time progress visibility
- Detailed step-by-step output
- All logs captured for troubleshooting
- Familiar Windows installer interface
- No external PowerShell windows

Everything happens **inside the MSI installer** with **full output transparency**!
