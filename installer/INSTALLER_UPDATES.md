# Installer Updates - MIT License and .env Configuration

This document summarizes the updates made to the Windows MSI installer to add MIT License support and .env file configuration capabilities.

## Summary of Changes

### 1. MIT License Integration

#### Files Created:
- [LICENSE](../LICENSE) - Plain text MIT License for the repository
- [installer/windows/LICENSE.rtf](windows/LICENSE.rtf) - RTF formatted MIT License for WiX installer

#### Files Modified:
- [installer/windows/Product.wxs](windows/Product.wxs#L72)
  - Added `WixUILicenseRtf` variable to reference LICENSE.rtf
  - License agreement is now displayed during installation

- [installer/windows/build-msi.ps1](windows/build-msi.ps1#L90-L97)
  - Updated to copy LICENSE.rtf from installer/windows directory
  - Added validation to ensure LICENSE.rtf exists before building

### 2. .env File Configuration During Installation

#### Files Created:
- [installer/windows/CustomUI.wxs](windows/CustomUI.wxs) - Custom WiX dialog for .env configuration
  - Provides two options:
    1. Paste .env file contents during installation
    2. Configure later using interactive wizard (recommended)
  - Includes multi-line text input for pasting .env contents
  - Integrates into installation flow after license agreement

- [installer/windows/scripts/create-env-from-input.ps1](windows/scripts/create-env-from-input.ps1) - PowerShell script to create .env file
  - Called as WiX custom action during installation
  - Creates .env file from user-provided content or template
  - Logs to `%TEMP%\dis-genai-install.log` for troubleshooting

- [installer/windows/EnvConfigDialog.wxs](windows/EnvConfigDialog.wxs) - Standalone dialog definition (used as reference)

#### Files Modified:
- [installer/windows/Product.wxs](windows/Product.wxs)
  - Lines 35-36: Added ENV_CONFIG_OPTION and ENV_FILE_CONTENT properties
  - Lines 67-77: Added custom action to create .env file from user input
  - Lines 80-82: Added custom action execution in InstallExecuteSequence
  - Line 90: Changed UI reference from WixUI_InstallDir to CustomInstallDir

- [installer/windows/scripts/setup-env.ps1](windows/scripts/setup-env.ps1#L48-L123)
  - Enhanced with 4 configuration options when .env exists:
    1. Keep existing configuration
    2. Reconfigure interactively
    3. Import from pasted .env contents
    4. Import from file browser selection
  - All reconfiguration options create timestamped backups
  - Added file browser dialog using System.Windows.Forms

- [installer/windows/build-msi.ps1](windows/build-msi.ps1)
  - Line 107: Added create-env-from-input.ps1 to critical scripts verification
  - Lines 145-153: Added CustomUI.wxs to build process
  - Line 158: Updated wixFiles array to include CustomUI.wxs

### 3. Documentation

#### Files Created:
- [installer/windows/ENV_CONFIGURATION.md](windows/ENV_CONFIGURATION.md) - Complete guide for .env configuration
  - During installation options
  - Post-installation configuration methods
  - Interactive wizard features
  - Backup and restore procedures
  - Troubleshooting guide

- [installer/INSTALLER_UPDATES.md](INSTALLER_UPDATES.md) - This file

## Installation Flow

### New User Experience:

1. **License Agreement** - User accepts MIT License
2. **Environment Configuration Dialog** (NEW)
   - Option to paste .env contents or configure later
   - Default: Configure later (recommended)
3. **Installation Directory** - Select installation path
4. **Installation** - Files copied and .env created
5. **Post-Install Wizard** - Interactive environment setup (if enabled)

### Existing User Experience (with .env):

1. **License Agreement** - User accepts MIT License
2. **Environment Configuration Dialog** - Can paste new .env or skip
3. **Installation** - .env updated or kept as-is
4. **Post-Install Wizard** - Options to keep, reconfigure, or import new .env

## Configuration Methods

### Method 1: During Installation (MSI Dialog)
- Paste complete .env file contents into installer dialog
- Best for: Users migrating from another installation
- Location: After license agreement, before directory selection

### Method 2: Post-Installation Wizard (Recommended)
- Interactive guided setup
- Prompts for API keys, database password, model selection
- Best for: New users, first-time installations
- Accessible via Start Menu or post-install prompt

### Method 3: Manual Reconfiguration
- Run setup-env.ps1 from Start Menu or command line
- 4 options: Keep, Reconfigure, Paste, or Browse for file
- Best for: Updating existing configurations

### Method 4: Direct File Edit
- Edit .env file directly in installation directory
- Best for: Advanced users, minor tweaks
- Location: `C:\Program Files\GenAI Research\.env`

## Technical Details

### WiX Custom Action Sequence:
1. User completes installation dialog sequence
2. `SetCreateEnvCommand` (immediate) - Prepares PowerShell command
3. `CreateEnvFile` (deferred) - Executes PowerShell script
4. Script creates .env from user input or template
5. Installation completes
6. Optional: `LaunchSetupWizard` runs post-install script

### Properties Flow:
- `ENV_CONFIG_OPTION` - "PASTE" or "LATER" (default)
- `ENV_FILE_CONTENT` - User-provided .env contents
- Both properties passed to create-env-from-input.ps1

### Backup Strategy:
- Format: `.env.backup.YYYYMMDD_HHMMSS`
- Created before any modification
- Never automatically deleted
- Allows rollback to previous configurations

## Testing Checklist

- [ ] Fresh installation with "Configure later" option
- [ ] Fresh installation with pasted .env contents
- [ ] Upgrade installation preserving existing .env
- [ ] License agreement displays correctly
- [ ] Post-install wizard all 4 options
- [ ] Backup files created with correct timestamps
- [ ] create-env-from-input.ps1 logging works
- [ ] Start Menu shortcuts work
- [ ] Build process includes all new files
- [ ] MSI installs without errors on clean Windows system

## Known Limitations

1. **Multi-line text input in WiX**: The Edit control with `Multiline="yes"` may have limited editing capabilities compared to a full text editor
2. **PowerShell execution policy**: Some systems may require adjusting execution policy
3. **File browser in setup-env.ps1**: Requires System.Windows.Forms assembly (standard in Windows)

## Future Enhancements

- [ ] Validate .env contents during installation
- [ ] Option to test API keys during setup
- [ ] Import .env from URL
- [ ] Export current configuration
- [ ] Configuration templates for common setups
- [ ] Integration with secrets management tools

## Migration Notes

### For Existing Installations:
- Existing .env files are automatically preserved during upgrade
- Post-install wizard detects existing .env and offers options
- All modifications create automatic backups

### For Build Systems:
- Ensure installer/windows/LICENSE.rtf exists
- Ensure installer/windows/CustomUI.wxs is included in build
- WiX Toolset 3.x required (tested with 3.11)

## References

- [WiX Toolset Documentation](https://wixtoolset.org/documentation/)
- [MIT License](https://opensource.org/licenses/MIT)
- [.env File Format](https://github.com/motdotla/dotenv)

## Contributors

Changes made as part of installer improvement initiative to:
1. Add proper MIT License to comply with open source requirements
2. Simplify .env configuration for both new and existing users
3. Provide multiple configuration methods for different user preferences

---
Last Updated: 2024-11-23
