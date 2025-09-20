#!/usr/bin/env python3
"""Test MCP initialization and tool listing"""

import httpx
import json

def test_mcp_init():
    """Test MCP initialization and list tools"""
    
    # Initialize session
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "tools": {},
                "prompts": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        },
        "id": 1
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    print("Sending initialize request...")
    with httpx.Client() as client:
        response = client.post(
            "http://localhost:8000/mcp/sse",
            json=init_request,
            headers=headers
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        # Parse SSE response
        for line in response.text.split('\n'):
            if line.startswith('data: '):
                data = json.loads(line[6:])
                print(f"Response data: {json.dumps(data, indent=2)}")
                
                if "result" in data:
                    print("\n✅ Initialization successful!")
                    print(f"Server name: {data['result']['serverInfo']['name']}")
                    print(f"Server version: {data['result']['serverInfo']['version']}")
                    
                    # Get session ID from result
                    session_id = data.get("result", {}).get("meta", {}).get("sessionId")
                    if session_id:
                        print(f"Session ID: {session_id}")
                        return session_id
                    
                elif "error" in data:
                    print(f"\n❌ Error: {data['error']}")
                    return None
    
    return None

def test_list_tools(session_id):
    """List available tools"""
    
    list_request = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 2
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-Session-ID": session_id  # Include session ID
    }
    
    print(f"\nListing tools with session {session_id}...")
    with httpx.Client() as client:
        response = client.post(
            "http://localhost:8000/mcp/sse",
            json=list_request,
            headers=headers
        )
        
        # Parse SSE response
        for line in response.text.split('\n'):
            if line.startswith('data: '):
                data = json.loads(line[6:])
                
                if "result" in data:
                    tools = data['result'].get('tools', [])
                    print(f"\n✅ Found {len(tools)} tools")
                    
                    # Check for notion_agent
                    for tool in tools:
                        if 'notion' in tool['name'].lower():
                            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                    
                    return tools
                    
                elif "error" in data:
                    print(f"\n❌ Error listing tools: {data['error']}")
                    return None
    
    return None

if __name__ == "__main__":
    session_id = test_mcp_init()
    if session_id:
        test_list_tools(session_id)