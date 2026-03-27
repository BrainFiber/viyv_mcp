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
                'ref': {
                    'type': 'string',
                    'description': 'Element reference ID to capture',
                },
                'region': {
                    'type': 'array',
                    'items': {'type': 'number'},
                    'minItems': 4,
                    'maxItems': 4,
                    'description': 'Capture region [x0, y0, x1, y1]',
                },
                'format': {
                    'type': 'string',
                    'enum': ['jpeg', 'png'],
                    'description': 'Image format (default: jpeg)',
                },
                'quality': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 100,
                    'description': 'JPEG quality (default: 80)',
                },
                'fullPage': {
                    'type': 'boolean',
                    'description': 'Capture full scrollable page (default: false). Ignored if ref or region is provided.',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'click',
        'description': 'Click on an element in the specified tab. Provide coordinate [x,y] or ref.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'coordinate': {
                    'type': 'array',
                    'items': {'type': 'number'},
                    'minItems': 2,
                    'maxItems': 2,
                    'description': 'Click position [x, y]',
                },
                'ref': {
                    'type': 'string',
                    'description': 'Element reference ID from read_page or find',
                },
                'action': {
                    'type': 'string',
                    'enum': ['left_click', 'right_click', 'double_click', 'triple_click'],
                    'description': 'Click type (default: left_click)',
                },
                'modifiers': {
                    'type': 'string',
                    'description': 'Modifier keys (e.g. "ctrl+shift")',
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
        'description': 'Get accessibility tree of the specified tab',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'filter': {
                    'type': 'string',
                    'enum': ['interactive', 'all'],
                    'description': 'Filter: "interactive" for buttons/links/inputs, "all" for everything',
                },
                'depth': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 20,
                    'description': 'Max tree depth (default: 15)',
                },
                'maxChars': {
                    'type': 'integer',
                    'description': 'Max output characters (default: 50000)',
                },
                'refId': {
                    'type': 'string',
                    'description': 'Focus on a specific element by ref',
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
        'description': 'Scroll the page in the specified tab. Provide coordinate+direction or ref.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'coordinate': {
                    'type': 'array',
                    'items': {'type': 'number'},
                    'minItems': 2,
                    'maxItems': 2,
                    'description': 'Scroll position [x, y]',
                },
                'direction': {
                    'type': 'string',
                    'enum': ['up', 'down', 'left', 'right'],
                    'description': 'Scroll direction',
                },
                'amount': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 10,
                    'description': 'Scroll amount (default: 3)',
                },
                'ref': {
                    'type': 'string',
                    'description': 'Element reference ID to scroll into view',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'find',
        'description': 'Find elements on the page using a natural language query',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'query': {
                    'type': 'string',
                    'description': 'Natural language description of what to find',
                },
            },
            'required': ['tabId', 'query'],
        },
    },
    {
        'name': 'hover',
        'description': 'Hover over an element in the specified tab. Provide coordinate [x,y] or ref.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'coordinate': {
                    'type': 'array',
                    'items': {'type': 'number'},
                    'minItems': 2,
                    'maxItems': 2,
                    'description': 'Hover position [x, y]',
                },
                'ref': {
                    'type': 'string',
                    'description': 'Element reference ID from read_page or find',
                },
            },
            'required': ['tabId'],
        },
    },
    {
        'name': 'key',
        'description': 'Press keyboard key(s) in the specified tab. Space-separated key names.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'tabId': {
                    'type': 'integer',
                    'description': 'Tab ID (from tabs_create or tabs_context)',
                },
                'keys': {
                    'type': 'string',
                    'description': 'Space-separated keys (e.g. "Enter", "ctrl+a")',
                },
                'repeat': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 100,
                    'description': 'Repeat count (default: 1)',
                },
            },
            'required': ['tabId', 'keys'],
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
                'navigation': {
                    'type': 'boolean',
                    'description': 'Wait for navigation to complete',
                },
                'timeout': {
                    'type': 'integer',
                    'description': 'Timeout in ms (default: 30000)',
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
                'startCoordinate': {
                    'type': 'array',
                    'items': {'type': 'number'},
                    'minItems': 2,
                    'maxItems': 2,
                    'description': 'Start position [x, y]',
                },
                'endCoordinate': {
                    'type': 'array',
                    'items': {'type': 'number'},
                    'minItems': 2,
                    'maxItems': 2,
                    'description': 'End position [x, y]',
                },
            },
            'required': ['tabId', 'startCoordinate', 'endCoordinate'],
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
        _register_tool_bridge(
            mcp, session, tool_info, tag_set, 'Browser',
            cfg_namespace='browser', cfg_security_level=1,
        )
        registered.append(tool_def['name'])

    logger.info(f"[relay:{session.key_prefix}] Registered {len(registered)} browser tools")
    return registered
