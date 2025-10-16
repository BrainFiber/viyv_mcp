# Suggested Commands for viyv_mcp Development

## Core Package Development

### Installation and Setup
```bash
# Install dependencies using uv
uv sync

# Install package in development/editable mode
pip install -e .

# Install in example project (from example/test or example/claude_code_mcp)
cd example/test
uv pip install -e ../../  # Install viyv_mcp from parent directory
```

### Testing
```bash
# Run all tests with pytest
pytest

# Run tests with asyncio support (configured in pyproject.toml)
pytest --asyncio-mode=auto

# Run specific test file
pytest test/test_mcp_protocol.py

# Run with verbose output
pytest -v

# Run with debug logging
LOG_LEVEL=DEBUG pytest
```

### Building and Publishing

```bash
# Clean build artifacts
rm -rf dist/ build/ *.egg-info

# Build the package
python -m build

# Install build tools if needed
pip install build twine

# Test upload to TestPyPI (optional)
twine upload --repository testpypi dist/*

# Production upload to PyPI
twine upload dist/*

# Install built wheel locally for testing
pip install dist/viyv_mcp-0.1.12-py3-none-any.whl
```

### Project Generation
```bash
# Create new MCP server project
create-viyv-mcp new my_mcp_server

# Navigate and setup
cd my_mcp_server
uv sync
```

## Generated Project Commands

### Development Server
```bash
# Run server (single worker)
uv run python main.py

# Run with debug logging
LOG_LEVEL=DEBUG uv run python main.py

# Run with stateless HTTP mode (for multi-worker support)
STATELESS_HTTP=true uv run python main.py
```

### Production Deployment
```bash
# Install gunicorn for multi-worker support
uv pip install gunicorn

# Run with multiple workers (stateless mode required)
STATELESS_HTTP=true uv run gunicorn test_app:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000

# Docker build and run
docker build -t my-mcp-server .
docker run -p 8000:8000 my-mcp-server
```

### Server Testing
```bash
# Health check
curl http://localhost:8000/health

# Test MCP endpoint (requires MCP client)
# Default server runs on http://0.0.0.0:8000 or http://127.0.0.1:8000
```

## Version Management

### Update Version
```bash
# Update version in multiple places (IMPORTANT: keep in sync!)
# 1. pyproject.toml - version = "0.1.X"
# 2. viyv_mcp/__init__.py - __version__ = "0.1.X"

# Check current version
python -c "from viyv_mcp import __version__; print(__version__)"
```

## macOS/Darwin System Commands

### File Operations
```bash
# List files (including hidden)
ls -la

# Find files by name
find . -name "*.py"

# Search in files (using ripgrep if available, or grep)
rg "pattern" --type py
# or
grep -r "pattern" --include="*.py" .

# Change directory
cd /path/to/directory

# Make directory
mkdir -p path/to/new/dir

# Remove files/directories
rm -rf directory_name
```

### Process Management
```bash
# List running processes
ps aux | grep python

# Kill process by PID
kill -9 <PID>

# Find process using port
lsof -i :8000

# Kill process on port
kill -9 $(lsof -t -i:8000)
```

### Python Environment
```bash
# Check Python version
python --version
python3 --version

# Check installed packages
pip list
uv pip list

# Show package info
pip show viyv_mcp

# Check uv version
uv --version
```

### Git Operations
```bash
# Check status
git status

# View recent commits
git log --oneline -10

# Create and push tag
git tag v0.1.12
git push origin v0.1.12

# View changes
git diff
git diff --cached  # staged changes
```

## Useful Utilities

### Package Information
```bash
# Check dependencies
uv pip list | grep fastmcp
uv pip list | grep starlette

# Verify installation
python -c "import viyv_mcp; print(viyv_mcp.__version__)"
python -c "from viyv_mcp import ViyvMCP; print('OK')"
```

### Debugging
```bash
# Run Python with verbose imports
python -v -c "import viyv_mcp"

# Interactive Python shell
python
>>> from viyv_mcp import ViyvMCP
>>> help(ViyvMCP)

# Check logs
tail -f logs/app.log  # if logging to file
```

### File Management
```bash
# Check file permissions
ls -l filename

# Change permissions
chmod +x script.sh

# Create temporary directory
mkdir -p tmp/experiment

# Move to temporary location
mv old_script.py tmp/
```

## Environment Variables

### Common Settings
```bash
# Server configuration
export HOST=0.0.0.0
export PORT=8000
export STATELESS_HTTP=true

# Logging
export LOG_LEVEL=DEBUG  # or INFO, WARNING, ERROR

# Directories
export BRIDGE_CONFIG_DIR=app/mcp_server_configs
export STATIC_DIR=static/images

# Integration keys
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_SIGNING_SECRET=...
export OPENAI_API_KEY=sk-...
```

### Load from .env file
```bash
# Load environment variables
source .env

# Or use dotenv in Python
python
>>> from dotenv import load_dotenv
>>> load_dotenv()
```

## Quick Reference

### Daily Development Workflow
```bash
# 1. Install/update dependencies
uv sync

# 2. Run tests
pytest

# 3. Run development server
uv run python main.py

# 4. Make changes and test
# ... edit code ...

# 5. When ready to release
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/*
```

### Example Project Testing
```bash
# Go to example project
cd example/test

# Install viyv_mcp in editable mode
uv pip install -e ../../

# Run the test server
STATELESS_HTTP=true uv run python main.py

# In another terminal, test endpoints
curl http://localhost:8000/health
```
