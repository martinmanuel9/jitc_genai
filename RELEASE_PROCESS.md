# Release Process for GenAI Research

## Quick Reference

**Repository:** https://github.com/martinmanuel9/jitc_genai
**Releases:** https://github.com/martinmanuel9/jitc_genai/releases

## Two Ways to Create a Release

### Method 1: Merge to Main (Recommended) ⭐
Automatically builds when VERSION file changes on main branch.
- ✅ **Simplest:** Just update VERSION and push to main
- ✅ **Fewer commands:** No need to create/push tags
- ✅ **Less error-prone:** No tag conflicts or mistakes
- ✅ **Best for:** Regular releases, team workflows

### Method 2: Git Tag
Manually create a tag to trigger builds.
- ✅ **Explicit version marking:** Tag in git history
- ✅ **Traditional workflow:** Familiar to many developers
- ✅ **Best for:** Hotfixes, marking specific commits

**Recommendation:** Use Method 1 for most releases. Use Method 2 only if you specifically need git tags.

---

## Method 1: Merge to Main (Recommended)

This is the simplest workflow - just update VERSION and merge to main.

### Step 1: Update Version and Changelog

```bash
# Update version number
echo "1.0.1" > VERSION

# Update changelog
nano CHANGELOG.md
```

Add new section to CHANGELOG.md:
```markdown
## [1.0.1] - 2025-11-15

### Added
- New feature description

### Fixed
- Bug fix description

### Changed
- Changes to existing functionality
```

### Step 2: Commit and Push to Main

```bash
git add VERSION CHANGELOG.md
git commit -m "Release version 1.0.1"
git push origin main
```

**That's it!** GitHub Actions will automatically detect the VERSION file change and build installers.

### Step 3: Monitor Build

1. Go to https://github.com/martinmanuel9/jitc_genai/actions
2. Watch the "Build Installers" workflow
3. Wait for all jobs to complete (~10-15 minutes)

### Step 4: Verify Release

1. Go to https://github.com/martinmanuel9/jitc_genai/releases
2. Verify the new release is created with all assets:
   - ✅ `genai-research-1.0.1.msi` (Windows)
   - ✅ `genai-research_1.0.1_amd64.deb` (Debian/Ubuntu)
   - ✅ `genai-research-1.0.1.x86_64.rpm` (RHEL/CentOS/Fedora)
   - ✅ `genai-research-1.0.1.dmg` (macOS)
   - ✅ `checksums-sha256.txt`

### Step 5: Test Installers (Recommended)

Download and test each installer before announcing to customers.

---

## Method 2: Git Tag

This method creates a tag to trigger the build.

### Step 1: Update Version and Changelog

```bash
# Update version number
echo "1.0.1" > VERSION

# Update changelog
nano CHANGELOG.md
```

Add new section to CHANGELOG.md as shown in Method 1.

### Step 2: Commit Changes

```bash
git add VERSION CHANGELOG.md
git commit -m "Release version 1.0.1"
git push origin main
```

### Step 3: Create and Push Tag

```bash
# Create annotated tag
git tag -a v1.0.1 -m "Release version 1.0.1"

# Push tag to GitHub
git push origin v1.0.1
```

### Step 4: Monitor and Verify

Same as Method 1 steps 3-5.

---

## Manual Build (Without Creating Release)

Use GitHub Actions workflow dispatch:

1. Go to https://github.com/martinmanuel9/jitc_genai/actions
2. Select "Build Installers" workflow
3. Click "Run workflow"
4. Enter version (e.g., "1.0.1-beta")
5. Click "Run workflow"

This builds installers without creating a GitHub release or git tag.

## Local Testing Before Release

Test installers locally before pushing tags:

```bash
# Build all packages
./installer/build-local.sh all

# Test specific package
./installer/build-local.sh deb    # Debian/Ubuntu
./installer/build-local.sh rpm    # RHEL/CentOS/Fedora
./installer/build-local.sh dmg    # macOS (macOS only)

# Output will be in dist/ directory
ls -lh dist/
```

## Customer Download Instructions

Share this URL with customers:

**Release Page:**
https://github.com/martinmanuel9/jitc_genai/releases

**Quick Start Guide:**
https://github.com/martinmanuel9/jitc_genai/blob/main/QUICKSTART.md

**Installation Guide:**
https://github.com/martinmanuel9/jitc_genai/blob/main/INSTALL.md

## Version Numbering Guidelines

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- **MAJOR:** Breaking changes (e.g., 1.0.0 → 2.0.0)
- **MINOR:** New features, backwards compatible (e.g., 1.0.0 → 1.1.0)
- **PATCH:** Bug fixes, backwards compatible (e.g., 1.0.0 → 1.0.1)

### Examples:

```bash
# Bug fix release
echo "1.0.1" > VERSION
git tag v1.0.1

# New feature release
echo "1.1.0" > VERSION
git tag v1.1.0

# Breaking change release
echo "2.0.0" > VERSION
git tag v2.0.0

# Beta/RC releases (for testing)
echo "1.1.0-beta.1" > VERSION
# Use manual workflow dispatch, don't create tag
```

## Rollback Process

If a release has issues:

### Option 1: Create Hotfix Release

```bash
# Fix the issue
# ... make fixes ...

# Create patch release
echo "1.0.2" > VERSION
git add .
git commit -m "Hotfix: Fix critical issue"
git tag v1.0.2
git push origin main v1.0.2
```

### Option 2: Delete Bad Release

```bash
# Delete GitHub release (via web UI)
# Go to Releases → Click release → Delete

# Delete tag
git tag -d v1.0.1
git push origin :refs/tags/v1.0.1
```

## Announcement Template

After release is published, announce to customers:

```
Subject: GenAI Research v1.0.1 Released

We're pleased to announce the release of GenAI Research v1.0.1!

Download: https://github.com/martinmanuel9/jitc_genai/releases

What's New:
- [List key features/fixes from CHANGELOG.md]

Installation:
See our Quick Start Guide for installation instructions:
https://github.com/martinmanuel9/jitc_genai/blob/main/QUICKSTART.md

Upgrade Instructions:
If you're upgrading from a previous version:
1. Download the new installer
2. Run the installer (your data will be preserved)
3. Restart services

Questions? Email support@example.com
```

## Troubleshooting

### Build Fails on GitHub Actions

**Check workflow logs:**
1. Go to Actions tab
2. Click failed workflow run
3. Click failed job
4. Review error messages

**Common issues:**
- VERSION file has extra whitespace (should be single line)
- Missing files referenced in installer configs
- WiX syntax errors in Product.wxs
- DEBIAN control file format issues

### Tag Already Exists

If you try to create a tag that already exists:

```bash
# Delete local tag
git tag -d v1.0.1

# Delete remote tag
git push origin :refs/tags/v1.0.1

# Create new tag
git tag -a v1.0.1 -m "Release version 1.0.1"
git push origin v1.0.1
```

### Installers Missing Features

If installers don't include new features:

1. Verify files are committed to git
2. Check .dockerignore and .gitignore don't exclude needed files
3. Rebuild and test locally first

## File Checklist Before Release

- [ ] VERSION file updated
- [ ] CHANGELOG.md updated with new version section
- [ ] All changes committed to git
- [ ] All tests passing (if you have tests)
- [ ] Documentation updated (if needed)
- [ ] .env.template includes any new variables
- [ ] docker-compose.yml updated (if services changed)

## Post-Release Tasks

- [ ] Test installers on each platform
- [ ] Update documentation if needed
- [ ] Announce to customers
- [ ] Monitor for issues
- [ ] Update internal documentation
- [ ] Close related GitHub issues
- [ ] Update roadmap/project board

## Emergency Hotfix Process

For critical bugs in production:

```bash
# 1. Create hotfix branch from tag
git checkout -b hotfix/1.0.1 v1.0.0

# 2. Fix the issue
# ... make fixes ...

# 3. Test thoroughly

# 4. Update VERSION and CHANGELOG
echo "1.0.1" > VERSION
# Update CHANGELOG.md

# 5. Commit and tag
git commit -am "Hotfix: [description]"
git tag v1.0.1

# 6. Merge back to main
git checkout main
git merge hotfix/1.0.1
git push origin main v1.0.1

# 7. Delete hotfix branch
git branch -d hotfix/1.0.1
```

## References

- **Semantic Versioning:** https://semver.org/
- **Keep a Changelog:** https://keepachangelog.com/
- **GitHub Releases:** https://docs.github.com/en/repositories/releasing-projects-on-github
- **WiX Toolset:** https://wixtoolset.org/
- **Debian Packaging:** https://www.debian.org/doc/manuals/maint-guide/

## Support

For questions about the release process:
- Open an issue: https://github.com/martinmanuel9/jitc_genai/issues
- Email: support@example.com
