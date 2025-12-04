# Quick Release Guide

## TL;DR - Fastest Way to Release

```bash
# 1. Update version
echo "1.0.1" > VERSION

# 2. Update changelog
nano CHANGELOG.md  # Add your changes

# 3. Commit and push
git add VERSION CHANGELOG.md
git commit -m "Release version 1.0.1"
git push origin main

# 4. Done!
# GitHub Actions automatically builds all installers.
# Check: https://github.com/martinmanuel9/jitc_genai/actions
```

---

## How It Works

**Trigger:** When you push a change to the `VERSION` file on the `main` branch

**What Happens:**
1. GitHub Actions detects VERSION file changed
2. Reads version from VERSION file (e.g., "1.0.1")
3. Builds installers for all platforms:
   - Windows MSI
   - Linux DEB (Debian/Ubuntu)
   - Linux RPM (RHEL/CentOS/Fedora)
   - macOS DMG
4. Creates GitHub Release at: https://github.com/martinmanuel9/jitc_genai/releases
5. Uploads all installers as downloadable assets
6. Generates SHA256 checksums

**Time:** ~10-15 minutes total

---

## Example: Bug Fix Release

```bash
# Current version: 1.0.0
# Fix a bug, then release 1.0.1

# 1. Fix the bug
git checkout -b fix/database-connection
# ... make fixes ...
git commit -m "Fix database connection timeout"

# 2. Update version for release
echo "1.0.1" > VERSION

# 3. Update changelog
cat >> CHANGELOG.md <<EOF

## [1.0.1] - $(date +%Y-%m-%d)

### Fixed
- Fixed database connection timeout issue
EOF

# 4. Commit version bump
git add VERSION CHANGELOG.md
git commit -m "Release version 1.0.1"

# 5. Merge to main
git checkout main
git merge fix/database-connection
git push origin main

# 6. GitHub Actions builds installers automatically!
```

---

## Example: New Feature Release

```bash
# Current version: 1.0.0
# Add new feature, then release 1.1.0

# 1. Develop feature
git checkout -b feature/ai-templates
# ... develop feature ...
git commit -m "Add AI template selection feature"

# 2. Update version for release
echo "1.1.0" > VERSION

# 3. Update changelog
cat >> CHANGELOG.md <<EOF

## [1.1.0] - $(date +%Y-%m-%d)

### Added
- New AI template selection feature for test plans
- Support for custom template configurations

### Improved
- Better error messages in UI
EOF

# 4. Commit version bump
git add VERSION CHANGELOG.md
git commit -m "Release version 1.1.0"

# 5. Merge to main
git checkout main
git merge feature/ai-templates
git push origin main

# 6. GitHub Actions builds installers automatically!
```

---

## Workflow Comparison

### Old Way (with tags):
```bash
echo "1.0.1" > VERSION
git add VERSION CHANGELOG.md
git commit -m "Release 1.0.1"
git push origin main
git tag v1.0.1           # Extra step
git push origin v1.0.1   # Extra step
```

### New Way (automatic):
```bash
echo "1.0.1" > VERSION
git add VERSION CHANGELOG.md
git commit -m "Release 1.0.1"
git push origin main
# Done! No tags needed.
```

---

## Monitoring the Build

**GitHub Actions:**
https://github.com/martinmanuel9/jitc_genai/actions

You'll see:
- ✅ "Build Installers" workflow running
- ✅ 6 jobs executing in parallel:
  - Prepare Release
  - Build Windows Installer
  - Build Linux DEB
  - Build Linux RPM
  - Build macOS DMG
  - Generate Checksums

**When Complete:**
https://github.com/martinmanuel9/jitc_genai/releases

You'll see:
- ✅ New release created (e.g., "Release v1.0.1")
- ✅ 5 downloadable assets
- ✅ Release notes from CHANGELOG.md

---

## Troubleshooting

### Build doesn't trigger
**Check:**
1. Did you push to `main` branch?
2. Did the `VERSION` file actually change?
3. Is VERSION file formatted correctly? (single line, no extra whitespace)

**Fix:**
```bash
# Verify VERSION file
cat VERSION  # Should show just: 1.0.1

# Force trigger by making a small change
echo "1.0.1" > VERSION
git add VERSION
git commit --amend --no-edit
git push origin main --force
```

### Build fails
**Check GitHub Actions logs:**
1. Go to Actions tab
2. Click the failed workflow
3. Click the failed job
4. Read error messages

**Common issues:**
- VERSION file has wrong format (use: `1.0.1` not `v1.0.1`)
- Missing files referenced in installer configs
- Syntax errors in WiX/DEB/RPM files

### Wrong version built
**The version comes from the VERSION file, not the commit message.**

Make sure VERSION file contains the correct version:
```bash
cat VERSION  # Should show: 1.0.1
```

---

## Advanced: Using Tags (Optional)

If you prefer to use git tags (for marking commits), you can still do that:

```bash
# Standard release
echo "1.0.1" > VERSION
git add VERSION CHANGELOG.md
git commit -m "Release 1.0.1"
git push origin main

# Optionally tag the commit
git tag v1.0.1
git push origin v1.0.1

# Both triggers work! Tag is optional.
```

---

## Version Numbering Quick Reference

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Bug fix | PATCH | 1.0.0 → 1.0.1 |
| New feature (compatible) | MINOR | 1.0.0 → 1.1.0 |
| Breaking change | MAJOR | 1.0.0 → 2.0.0 |
| Beta release | Pre-release | 1.1.0-beta.1 |

---

## Full Documentation

For complete details, see:
- **RELEASE_PROCESS.md** - Detailed release procedures
- **installer/README.md** - Installer development
- **INSTALL.md** - Customer installation guide
