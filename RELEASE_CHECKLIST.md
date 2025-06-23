# Release Checklist for viyv_mcp v0.1.4

## Pre-release Steps
- [x] Update version in `pyproject.toml` (0.1.3 → 0.1.4)
- [x] Update version in `viyv_mcp/__init__.py` (0.1.2 → 0.1.4)
- [x] Create/Update CHANGELOG.md with release notes
- [x] Clean build artifacts (`rm -rf dist/ build/ *.egg-info`)

## Changes in v0.1.4
### Bug Fixes
- Fixed missing `entry` decorator export in `__init__.py`
- Fixed `auto_register_modules` to gracefully handle missing optional directories

### Improvements
- Better error handling for optional module directories (entries, resources, etc.)
- Added comprehensive claude_code_mcp example project

### Documentation
- Enhanced CLAUDE.md with development guidelines
- Added file placement guidelines for temporary/permanent scripts

## Build and Test
```bash
# Build the package
python -m build

# Test installation locally (optional)
pip install dist/viyv_mcp-0.1.4-py3-none-any.whl

# Or test with example project
cd example/claude_code_mcp
./setup.sh
uv run python main.py
```

## Publish to PyPI
```bash
# Test upload (optional)
twine upload --repository testpypi dist/*

# Production upload
twine upload dist/*
```

## Post-release
- [ ] Create GitHub release tag v0.1.4
- [ ] Update any dependent projects
- [ ] Announce release if needed

## Rollback Plan
If issues are found:
```bash
# Yank from PyPI (use with caution)
pip install twine
twine yank viyv_mcp==0.1.4

# Fix issues and release as 0.1.5
```