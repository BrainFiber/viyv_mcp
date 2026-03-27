"""WebSocket bridge session -- forwards tool calls to the Chrome extension."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ErrorData, ImageContent, TextContent
from starlette.websockets import WebSocket

from viyv_mcp.app.ws_bridge_protocol import ToolCallMessage, ToolResultMessage

logger = logging.getLogger(__name__)


class WebSocketBridgeSession:
    """Duck-type session compatible with bridge_manager._register_tool_bridge.

    Implements call_tool() by sending a tool_call message over WebSocket
    and waiting for the corresponding tool_result.
    """

    def __init__(self, ws: WebSocket, key: str) -> None:
        self._ws = ws
        self._key = key
        self._pending: dict[str, asyncio.Future[ToolResultMessage]] = {}
        self._key_prefix = key[:8] if len(key) >= 8 else key

    @property
    def key_prefix(self) -> str:
        return self._key_prefix

    async def call_tool(self, tool_name: str, arguments: dict | None = None):
        """Send tool_call to the Chrome extension and wait for tool_result."""
        call_id = uuid.uuid4().hex[:12]
        msg = ToolCallMessage(
            id=call_id,
            tool=tool_name,
            input=arguments or {},
            timestamp=int(time.time() * 1000),
        )

        fut: asyncio.Future[ToolResultMessage] = asyncio.get_running_loop().create_future()
        self._pending[call_id] = fut

        try:
            await self._ws.send_json(msg.model_dump())
            # Wait for result with timeout
            result = await asyncio.wait_for(fut, timeout=300)  # 5 min timeout
        except asyncio.TimeoutError:
            self._pending.pop(call_id, None)
            raise TimeoutError(f"Tool call '{tool_name}' timed out after 300s")
        except Exception:
            self._pending.pop(call_id, None)
            raise

        if not result.success:
            error_msg = (
                result.error.get('message', 'Unknown error')
                if result.error
                else 'Unknown error'
            )
            raise McpError(ErrorData(code=-32000, message=error_msg))

        # Convert result to MCP-compatible CallToolResult format
        result_data = result.result or {}

        # The tool result from the extension is usually {content: [...]} or plain data
        if 'content' in result_data and isinstance(result_data['content'], list):
            content_items = []
            for item in result_data['content']:
                if isinstance(item, dict):
                    if item.get('type') == 'image':
                        content_items.append(ImageContent(
                            type='image',
                            data=item.get('data', ''),
                            mimeType=item.get('mimeType', 'image/jpeg'),
                        ))
                    else:
                        content_items.append(TextContent(
                            type='text',
                            text=item.get('text', json.dumps(item)),
                        ))
                else:
                    content_items.append(TextContent(type='text', text=str(item)))
            return CallToolResult(content=content_items)

        # Detect image data (e.g. screenshot result: {data: "base64...", format: "jpeg"})
        if 'data' in result_data and result_data.get('format') in ('jpeg', 'png', 'gif', 'webp'):
            mime = f"image/{result_data['format']}"
            return CallToolResult(content=[
                ImageContent(type='image', data=result_data['data'], mimeType=mime),
            ])

        return ToolResult(
            content=[TextContent(type='text', text=json.dumps(result_data))],
        )

    def handle_message(self, data: dict) -> bool:
        """Handle an incoming message from the Chrome extension.

        Returns True if the message was handled (tool_result).
        """
        if data.get('type') == 'tool_result':
            call_id = data.get('id')
            fut = self._pending.pop(call_id, None)
            if fut and not fut.done():
                fut.set_result(ToolResultMessage(**data))
                return True
            else:
                logger.warning(
                    f"[ws-bridge:{self._key_prefix}] Unexpected tool_result id={call_id}"
                )
        return False

    async def close(self) -> None:
        """Cancel all pending futures."""
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
