#!/usr/bin/env python
"""Test app for running with workers and stateless_http"""
import os
from viyv_mcp import ViyvMCP
from app.config import Config

# Get stateless_http setting from environment
stateless_http = Config.get_stateless_http()
print(f"Starting server with stateless_http={stateless_http}")

# Create the app instance
app = ViyvMCP("My SSE MCP Server", stateless_http=stateless_http).get_app()