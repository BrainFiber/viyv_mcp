"""Per-key MCP handler -- custom JSON-RPC handler for relay connections."""
from __future__ import annotations

import logging

from fastmcp import FastMCP
from mcp import types

from viyv_mcp.app.bridge_manager import _register_tool_bridge
from viyv_mcp.app.ws_bridge_session import WebSocketBridgeSession

logger = logging.getLogger(__name__)

# Browser tools provided by viyv-browser Chrome extension
# These match the tool names registered in the extension's tool-handlers.ts
BROWSER_TOOLS = [
    {
        'name': 'navigate',
        'description': 'Navigate to a URL',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'url': {
                    'type': 'string',
                    'description': 'URL to navigate to',
                },
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID to navigate (optional)',
                },
                'waitUntil': {
                    'type': 'string',
                    'description': (
                        'Wait condition: load, domcontentloaded, networkidle'
                    ),
                },
            },
            'required': ['url'],
        },
    },
    {
        'name': 'screenshot',
        'description': 'Take a screenshot of the current page',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector to screenshot',
                },
                'fullPage': {
                    'type': 'boolean',
                    'description': 'Capture full page',
                },
            },
        },
    },
    {
        'name': 'click',
        'description': 'Click on an element',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector or text to click',
                },
                'x': {
                    'type': 'number',
                    'description': 'X coordinate',
                },
                'y': {
                    'type': 'number',
                    'description': 'Y coordinate',
                },
            },
        },
    },
    {
        'name': 'type',
        'description': 'Type text into an element',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector',
                },
                'text': {
                    'type': 'string',
                    'description': 'Text to type',
                },
            },
            'required': ['text'],
        },
    },
    {
        'name': 'read_page',
        'description': 'Read the content of the current page',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector to scope reading',
                },
            },
        },
    },
    {
        'name': 'get_page_text',
        'description': 'Get the text content of the page',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'maxLength': {
                    'type': 'integer',
                    'description': 'Max characters to return',
                },
            },
        },
    },
    {
        'name': 'tabs_context',
        'description': 'Get information about open browser tabs',
        'inputSchema': {
            'type': 'object',
            'properties': {},
        },
    },
    {
        'name': 'tabs_create',
        'description': 'Create a new browser tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'url': {
                    'type': 'string',
                    'description': 'URL to open',
                },
                'active': {
                    'type': 'boolean',
                    'description': 'Whether to make the tab active',
                },
            },
        },
    },
    {
        'name': 'javascript_exec',
        'description': 'Execute JavaScript in the page',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'code': {
                    'type': 'string',
                    'description': 'JavaScript code to execute',
                },
            },
            'required': ['code'],
        },
    },
    {
        'name': 'form_input',
        'description': 'Fill form fields',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector for the input',
                },
                'value': {
                    'type': 'string',
                    'description': 'Value to fill',
                },
            },
            'required': ['selector', 'value'],
        },
    },
    {
        'name': 'scroll',
        'description': 'Scroll the page',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'direction': {
                    'type': 'string',
                    'description': 'Scroll direction: up, down, left, right',
                },
                'amount': {
                    'type': 'integer',
                    'description': 'Scroll amount in pixels',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector of element to scroll',
                },
            },
        },
    },
    {
        'name': 'find',
        'description': 'Find elements on the page',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'text': {
                    'type': 'string',
                    'description': 'Text to find',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector to find',
                },
            },
        },
    },
    {
        'name': 'hover',
        'description': 'Hover over an element',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector',
                },
                'x': {
                    'type': 'number',
                    'description': 'X coordinate',
                },
                'y': {
                    'type': 'number',
                    'description': 'Y coordinate',
                },
            },
        },
    },
    {
        'name': 'key',
        'description': 'Press a keyboard key',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'key': {
                    'type': 'string',
                    'description': 'Key to press (e.g. Enter, Tab, Escape)',
                },
                'modifiers': {
                    'type': 'array',
                    'description': 'Modifier keys (ctrl, alt, shift, meta)',
                    'items': {'type': 'string'},
                },
            },
            'required': ['key'],
        },
    },
    {
        'name': 'select_tab',
        'description': 'Switch to a specific browser tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID to switch to',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'tab_close',
        'description': 'Close a browser tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID to close',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'wait_for',
        'description': 'Wait for a condition',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector to wait for',
                },
                'text': {
                    'type': 'string',
                    'description': 'Text to wait for',
                },
                'timeout': {
                    'type': 'integer',
                    'description': 'Timeout in milliseconds',
                },
            },
        },
    },
    {
        'name': 'drag',
        'description': 'Drag an element',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'from_x': {
                    'type': 'number',
                    'description': 'Start X coordinate',
                },
                'from_y': {
                    'type': 'number',
                    'description': 'Start Y coordinate',
                },
                'to_x': {
                    'type': 'number',
                    'description': 'End X coordinate',
                },
                'to_y': {
                    'type': 'number',
                    'description': 'End Y coordinate',
                },
            },
            'required': ['from_x', 'from_y', 'to_x', 'to_y'],
        },
    },
    {
        'name': 'read_console_messages',
        'description': 'Read browser console messages',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'pattern': {
                    'type': 'string',
                    'description': 'Regex pattern to filter messages',
                },
            },
        },
    },
    {
        'name': 'read_network_requests',
        'description': 'Read network requests',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'pattern': {
                    'type': 'string',
                    'description': 'URL pattern to filter',
                },
            },
        },
    },
    {
        'name': 'file_upload',
        'description': 'Upload a file to a file input',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector for file input',
                },
                'filePath': {
                    'type': 'string',
                    'description': 'Path to the file',
                },
            },
            'required': ['selector', 'filePath'],
        },
    },
    {
        'name': 'handle_dialog',
        'description': 'Handle a browser dialog (alert, confirm, prompt)',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'accept': {
                    'type': 'boolean',
                    'description': 'Accept or dismiss the dialog',
                },
                'text': {
                    'type': 'string',
                    'description': 'Text to enter for prompt dialogs',
                },
            },
        },
    },
    {
        'name': 'resize_window',
        'description': 'Resize the browser window',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'width': {
                    'type': 'integer',
                    'description': 'Window width',
                },
                'height': {
                    'type': 'integer',
                    'description': 'Window height',
                },
            },
            'required': ['width', 'height'],
        },
    },
    {
        'name': 'gif_creator',
        'description': 'Control GIF recording',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'action': {
                    'type': 'string',
                    'description': 'start, capture, or stop',
                },
                'filename': {
                    'type': 'string',
                    'description': 'Output filename',
                },
            },
            'required': ['action'],
        },
    },
    {
        'name': 'page_data_extract',
        'description': 'Extract structured data from the page',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector scope',
                },
                'format': {
                    'type': 'string',
                    'description': 'Output format: json, text, table',
                },
            },
        },
    },
    {
        'name': 'artifact_from_page',
        'description': 'Create an artifact from page content',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID',
                },
                'type': {
                    'type': 'string',
                    'description': 'Artifact type',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector',
                },
            },
            'required': ['type'],
        },
    },
]


def register_browser_tools_for_session(
    mcp: FastMCP,
    session: WebSocketBridgeSession,
    tags: set[str] | None = None,
) -> list[str]:
    """Register all browser tools backed by the given WS session.

    Returns list of registered tool names.
    """
    registered = []
    tag_set = tags or {'browser', 'relay'}

    for tool_def in BROWSER_TOOLS:
        tool_info = types.Tool(
            name=tool_def['name'],
            description=tool_def.get('description', ''),
            inputSchema=tool_def.get('inputSchema', {}),
        )
        _register_tool_bridge(mcp, session, tool_info, tag_set, 'Browser')
        registered.append(tool_def['name'])

    logger.info(f"[relay:{session.key_prefix}] Registered {len(registered)} browser tools")
    return registered
