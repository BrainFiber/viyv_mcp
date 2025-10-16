# Task Completion Checklist

## When a Development Task is Completed

### 1. Code Quality Checks
- [ ] Run linting/formatting (if configured)
- [ ] Ensure type hints are present for all functions
- [ ] Verify all imports are used
- [ ] Check for proper error handling
- [ ] Remove debug print statements
- [ ] Update docstrings if needed

### 2. Testing
```bash
# Run all tests
pytest

# Run with verbose output to catch issues
pytest -v

# If any tests fail, fix them before proceeding
```

### 3. Version Control
```bash
# Check what changed
git status
git diff

# Stage changes
git add <files>

# Commit with meaningful message
git commit -m "feat: description of changes"
# or
git commit -m "fix: description of bug fix"
# or
git commit -m "docs: description of documentation changes"
```

## Release Preparation Checklist

### Pre-Release Steps

#### 1. Version Update
- [ ] Update version in `pyproject.toml`
  ```toml
  version = "0.1.X"
  ```
- [ ] Update version in `viyv_mcp/__init__.py`
  ```python
  __version__ = "0.1.X"
  ```
- [ ] Ensure both versions match!

#### 2. Documentation
- [ ] Update CHANGELOG.md with release notes
  - List all new features (### Added)
  - List all bug fixes (### Fixed)
  - List all changes (### Changed)
  - List any breaking changes (### Breaking Changes)
- [ ] Update README.md if needed
  - New features should be documented
  - Update version badge if present
- [ ] Update CLAUDE.md if development workflow changed

#### 3. Clean and Verify
```bash
# Clean all build artifacts
rm -rf dist/ build/ *.egg-info

# Verify .gitignore is up to date
git status  # Should not show unwanted files
```

### Build and Test

#### 1. Build Package
```bash
# Build the package
python -m build

# Verify dist/ directory contains:
# - viyv_mcp-0.1.X-py3-none-any.whl
# - viyv_mcp-0.1.X.tar.gz
ls -la dist/
```

#### 2. Local Installation Test
```bash
# Test installation locally
pip install dist/viyv_mcp-0.1.X-py3-none-any.whl

# Verify it works
python -c "from viyv_mcp import ViyvMCP; print('OK')"
```

#### 3. Example Project Test
```bash
# Test with example project
cd example/test

# Install the new version
uv pip install ../../dist/viyv_mcp-0.1.X-py3-none-any.whl

# Run the server
STATELESS_HTTP=true uv run python main.py

# In another terminal, test endpoints
curl http://localhost:8000/health

# Stop the server when done (Ctrl+C)
```

### Publishing to PyPI

#### 1. Test Upload (Optional but Recommended)
```bash
# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ viyv_mcp==0.1.X
```

#### 2. Production Upload
```bash
# Make sure twine is installed
pip install twine

# Upload to production PyPI
twine upload dist/*

# Verify on PyPI
# Visit: https://pypi.org/project/viyv_mcp/
```

### Post-Release Steps

#### 1. Git Tagging
```bash
# Create version tag
git tag v0.1.X

# Push tag to remote
git push origin v0.1.X

# Push any remaining commits
git push
```

#### 2. GitHub Release (Optional)
- [ ] Create GitHub release at https://github.com/BrainFiber/viyv_mcp/releases
- [ ] Use tag v0.1.X
- [ ] Copy CHANGELOG.md content for release notes
- [ ] Attach wheel and source distribution files

#### 3. Update Dependent Projects
- [ ] Update version in any dependent projects
- [ ] Test dependent projects with new version
- [ ] Notify users if needed

#### 4. Communication
- [ ] Announce release if needed (Discord, Slack, etc.)
- [ ] Update documentation if hosted separately
- [ ] Close related GitHub issues with "Fixed in v0.1.X"

## Rollback Plan

### If Issues Are Found After Release

#### Option 1: Yank from PyPI
```bash
# Yank the problematic version (USE WITH CAUTION!)
pip install twine
twine yank viyv_mcp==0.1.X

# This marks the version as unavailable but doesn't delete it
```

#### Option 2: Quick Fix Release
```bash
# Fix the issues
# ... make fixes ...

# Increment to next version (0.1.X+1)
# Update pyproject.toml and __init__.py

# Build and release
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/*
```

## Quick Release Command Sequence

```bash
# 1. Update versions in pyproject.toml and __init__.py

# 2. Update CHANGELOG.md

# 3. Clean and build
rm -rf dist/ build/ *.egg-info
python -m build

# 4. Run tests
pytest

# 5. Test locally
cd example/test
uv pip install ../../dist/viyv_mcp-0.1.X-py3-none-any.whl
STATELESS_HTTP=true uv run python main.py
# Test, then Ctrl+C

# 6. Upload to PyPI
cd ../..
twine upload dist/*

# 7. Tag and push
git tag v0.1.X
git push origin v0.1.X
git push
```

## Important Notes

- **ALWAYS** test the package locally before publishing
- **NEVER** skip version updates in both pyproject.toml and __init__.py
- **VERIFY** that tests pass before releasing
- **CHECK** CHANGELOG.md is updated with all changes
- **TEST** with example projects to ensure compatibility
- **CREATE** GitHub release for better visibility
- **BACKUP** dist/ directory before uploading (keep wheel files)
