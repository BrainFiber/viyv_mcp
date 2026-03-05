"""Tests for WS Bridge feedback fixes.

Covers:
1. Double-wrap fix (ToolResult instead of CallToolResult)
2. ToolError on error responses (isError=True)
3. ImageContent detection for screenshots
4. tabId required fields in relay tool definitions
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult
from mcp.types import ImageContent, TextContent

from viyv_mcp.app.ws_bridge_protocol import ToolResultMessage
from viyv_mcp.app.ws_bridge_session import WebSocketBridgeSession
from viyv_mcp.app.relay_mcp_handler import BROWSER_TOOLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> tuple[WebSocketBridgeSession, AsyncMock]:
    """Create a WebSocketBridgeSession with a mocked WebSocket."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    session = WebSocketBridgeSession(ws, 'testkey12345')
    return session, ws


def _resolve_pending(session: WebSocketBridgeSession, result_msg: dict):
    """Simulate the Chrome extension replying to a pending tool call."""
    # Get the single pending call_id
    call_id = next(iter(session._pending))
    data = {'type': 'tool_result', 'id': call_id, **result_msg}
    session.handle_message(data)


# ---------------------------------------------------------------------------
# Fix 1: call_tool returns ToolResult (not CallToolResult)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_tool_returns_tool_result_with_text():
    """Success response returns FastMCP ToolResult, not mcp.types.CallToolResult."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        # After send, simulate reply
        _resolve_pending(session, {
            'success': True,
            'result': {'key': 'value'},
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    result = await session.call_tool('test_tool', {'arg': 1})

    assert isinstance(result, ToolResult), f'Expected ToolResult, got {type(result)}'
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    assert json.loads(result.content[0].text) == {'key': 'value'}


@pytest.mark.asyncio
async def test_call_tool_returns_tool_result_with_content_list():
    """Content list from extension is properly converted to ToolResult."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': True,
            'result': {
                'content': [
                    {'type': 'text', 'text': 'hello'},
                    {'type': 'text', 'text': 'world'},
                ],
            },
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    result = await session.call_tool('read_page', {'tabId': 1})

    assert isinstance(result, ToolResult)
    assert len(result.content) == 2
    assert result.content[0].text == 'hello'
    assert result.content[1].text == 'world'


# ---------------------------------------------------------------------------
# Fix 1b: Error responses raise ToolError (isError=True in MCP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_tool_raises_tool_error_on_failure():
    """Error response raises ToolError so MCP sets isError=True."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': False,
            'error': {'message': 'Tab not found'},
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    with pytest.raises(ToolError, match='Tab not found'):
        await session.call_tool('navigate', {'url': 'https://example.com'})


@pytest.mark.asyncio
async def test_call_tool_raises_tool_error_unknown_error():
    """Error without message field defaults to 'Unknown error'."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': False,
            'error': {},
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    with pytest.raises(ToolError, match='Unknown error'):
        await session.call_tool('click', {'tabId': 1})


@pytest.mark.asyncio
async def test_call_tool_raises_tool_error_null_error():
    """Error with null error field defaults to 'Unknown error'."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': False,
            'error': None,
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    with pytest.raises(ToolError, match='Unknown error'):
        await session.call_tool('click', {'tabId': 1})


# ---------------------------------------------------------------------------
# Fix 3: Screenshot ImageContent detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screenshot_returns_image_content():
    """Screenshot result {data, format} is returned as ImageContent."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': True,
            'result': {
                'data': 'base64screenshotdata',
                'format': 'jpeg',
                'imageId': 'ss_1',
            },
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    result = await session.call_tool('screenshot', {'tabId': 1})

    assert isinstance(result, ToolResult)
    assert len(result.content) == 1
    assert isinstance(result.content[0], ImageContent)
    assert result.content[0].data == 'base64screenshotdata'
    assert result.content[0].mimeType == 'image/jpeg'


@pytest.mark.asyncio
async def test_screenshot_png_format():
    """PNG format screenshot also returns ImageContent."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': True,
            'result': {
                'data': 'pngdata',
                'format': 'png',
            },
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    result = await session.call_tool('screenshot', {'tabId': 1})

    assert isinstance(result.content[0], ImageContent)
    assert result.content[0].mimeType == 'image/png'


@pytest.mark.asyncio
async def test_non_image_format_not_detected():
    """Data with non-image format (e.g. 'json') is NOT treated as image."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': True,
            'result': {
                'data': '{"key": "value"}',
                'format': 'json',
            },
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    result = await session.call_tool('page_data_extract', {'tabId': 1})

    assert isinstance(result, ToolResult)
    assert isinstance(result.content[0], TextContent)
    # Should be JSON-serialized, not ImageContent
    parsed = json.loads(result.content[0].text)
    assert parsed['format'] == 'json'


@pytest.mark.asyncio
async def test_content_list_with_image_items():
    """Content list containing image items converts properly."""
    session, ws = _make_session()

    async def _send_and_reply(msg):
        _resolve_pending(session, {
            'success': True,
            'result': {
                'content': [
                    {
                        'type': 'image',
                        'data': 'imgdata',
                        'mimeType': 'image/png',
                    },
                ],
            },
            'agentId': 'cloud',
        })

    ws.send_json.side_effect = _send_and_reply

    result = await session.call_tool('screenshot', {'tabId': 1})

    assert isinstance(result, ToolResult)
    assert isinstance(result.content[0], ImageContent)
    assert result.content[0].data == 'imgdata'
    assert result.content[0].mimeType == 'image/png'


# ---------------------------------------------------------------------------
# Fix 2: tabId required in relay tool definitions
# ---------------------------------------------------------------------------

# CDP tools that require tabId
CDP_TOOLS_REQUIRING_TAB_ID = {
    'navigate', 'screenshot', 'click', 'type', 'read_page', 'get_page_text',
    'javascript_exec', 'form_input', 'scroll', 'find', 'hover', 'key',
    'select_tab', 'tab_close', 'wait_for', 'drag', 'read_console_messages',
    'read_network_requests', 'file_upload', 'handle_dialog',
    'page_data_extract', 'artifact_from_page',
}

# Tools that should NOT require tabId
NO_TAB_ID_REQUIRED = {'tabs_context', 'tabs_create', 'resize_window', 'gif_creator'}


def _tool_by_name(name: str) -> dict:
    for t in BROWSER_TOOLS:
        if t['name'] == name:
            return t
    raise ValueError(f'Tool {name} not found')


def test_cdp_tools_require_tab_id():
    """All CDP tools have tabId in required."""
    for name in CDP_TOOLS_REQUIRING_TAB_ID:
        tool = _tool_by_name(name)
        required = tool['inputSchema'].get('required', [])
        assert 'tabId' in required, f'{name}: tabId should be required'


def test_non_cdp_tools_do_not_require_tab_id():
    """Tab management tools do NOT require tabId."""
    for name in NO_TAB_ID_REQUIRED:
        tool = _tool_by_name(name)
        required = tool['inputSchema'].get('required', [])
        assert 'tabId' not in required, f'{name}: tabId should NOT be required'


def test_tab_id_description_consistency():
    """All tabId property descriptions mention 'from tabs_create or tabs_context'."""
    for tool in BROWSER_TOOLS:
        props = tool.get('inputSchema', {}).get('properties', {})
        if 'tabId' in props:
            desc = props['tabId']['description']
            assert '(from tabs_create or tabs_context)' in desc, (
                f'{tool["name"]}: tabId description inconsistent: {desc}'
            )


def test_tabs_create_mentions_tab_id_return():
    """tabs_create description tells users about returned tabId."""
    tool = _tool_by_name('tabs_create')
    assert 'tabId' in tool['description']


def test_tabs_context_mentions_tab_id_return():
    """tabs_context description mentions tabId return."""
    tool = _tool_by_name('tabs_context')
    assert 'tabId' in tool['description']


def test_total_browser_tools_count():
    """Sanity check: expected number of browser tools."""
    assert len(BROWSER_TOOLS) == 26
