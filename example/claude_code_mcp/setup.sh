#!/bin/bash

# Setup script for claude_code_mcp example

echo "Setting up claude_code_mcp example..."

# Install other dependencies
echo "Installing dependencies..."
uv sync

# Install viyv_mcp in editable mode from parent directory
echo "Installing viyv_mcp in editable mode..."
uv pip install -e ../../

echo "Setup complete! Run with: uv run python main.py"