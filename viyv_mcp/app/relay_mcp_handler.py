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
        'description': 'Navigate to a URL in the specified tab. Use tabs_create first to get a tabId.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'url': {
                    'type': 'string',
                    'description': 'URL to navigate to',
                },
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'waitUntil': {
                    'type': 'string',
                    'description': (
                        'Wait condition: load, domcontentloaded, networkidle'
                    ),
                },
            },
            'required': ['url', 'tabId'],
        },
    },
    {
        'name': 'screenshot',
        'description': 'Take a screenshot of the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
        },
    },
    {
        'name': 'click',
        'description': 'Click on an element in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
        },
    },
    {
        'name': 'type',
        'description': 'Type text into an element in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId', 'text'],
        },
    },
    {
        'name': 'read_page',
        'description': 'Read the content of the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector to scope reading',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'get_page_text',
        'description': 'Get the text content of the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'maxLength': {
                    'type': 'integer',
                    'description': 'Max characters to return',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'tabs_context',
        'description': 'Get information about open browser tabs. Returns tabIds and URLs for each tab.',
        'inputSchema': {
            'type': 'object',
            'properties': {},
        },
    },
    {
        'name': 'tabs_create',
        'description': 'Create a new browser tab. Returns a tabId to use in subsequent tool calls.',
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
        'description': 'Execute JavaScript in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'code': {
                    'type': 'string',
                    'description': 'JavaScript code to execute',
                },
            },
            'required': ['tabId', 'code'],
        },
    },
    {
        'name': 'form_input',
        'description': 'Fill form fields in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId', 'selector', 'value'],
        },
    },
    {
        'name': 'scroll',
        'description': 'Scroll the page in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
        },
    },
    {
        'name': 'find',
        'description': 'Find elements on the page in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
        },
    },
    {
        'name': 'hover',
        'description': 'Hover over an element in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
        },
    },
    {
        'name': 'key',
        'description': 'Press a keyboard key in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId', 'key'],
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
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'wait_for',
        'description': 'Wait for a condition in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
        },
    },
    {
        'name': 'drag',
        'description': 'Drag an element in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId', 'from_x', 'from_y', 'to_x', 'to_y'],
        },
    },
    {
        'name': 'read_console_messages',
        'description': 'Read browser console messages from the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'pattern': {
                    'type': 'string',
                    'description': 'Regex pattern to filter messages',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'read_network_requests',
        'description': 'Read network requests from the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'pattern': {
                    'type': 'string',
                    'description': 'URL pattern to filter',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'file_upload',
        'description': 'Upload a file to a file input in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId', 'selector', 'filePath'],
        },
    },
    {
        'name': 'handle_dialog',
        'description': 'Handle a browser dialog (alert, confirm, prompt) in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
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
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
        'description': 'Extract structured data from the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId'],
        },
    },
    {
        'name': 'artifact_from_page',
        'description': 'Create an artifact from page content in the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
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
            'required': ['tabId', 'type'],
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
