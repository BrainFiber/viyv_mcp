"""Relay key manager -- create, validate, revoke keys with TTL and persistence."""
from __future__ import annotations

import json
import logging
import secrets
import time
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = logging.getLogger(__name__)


class RelayKeyManager:
    """Manages relay keys with TTL and optional file persistence."""

    def __init__(
        self,
        ttl_hours: float = 24,
        storage_path: str | None = None,
    ) -> None:
        self._ttl_seconds = ttl_hours * 3600
        self._storage_path = storage_path
        # key -> {created_at: float, label: str}
        self._keys: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self._keys = data.get('keys', {})
                # Prune expired
                now = time.time()
                expired = [
                    k for k, v in self._keys.items()
                    if now - v.get('created_at', 0) > self._ttl_seconds
                ]
                for k in expired:
                    del self._keys[k]
                logger.info(
                    f"[relay-keys] Loaded {len(self._keys)} keys "
                    f"(pruned {len(expired)} expired)"
                )
            except Exception as e:
                logger.warning(f"[relay-keys] Failed to load keys: {e}")

    def _save(self) -> None:
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'w') as f:
                json.dump({'keys': self._keys}, f, indent=2)
        except Exception as e:
            logger.warning(f"[relay-keys] Failed to save keys: {e}")

    def create_key(self, label: str = '') -> str:
        """Create a new relay key."""
        key = secrets.token_urlsafe(32)
        self._keys[key] = {
            'created_at': time.time(),
            'label': label,
        }
        self._save()
        logger.info(f"[relay-keys] Created key {key[:8]}... label='{label}'")
        return key

    def validate_key(self, key: str) -> bool:
        """Check if a key is valid (exists and not expired)."""
        info = self._keys.get(key)
        if not info:
            return False
        if time.time() - info.get('created_at', 0) > self._ttl_seconds:
            # Expired -- remove it
            del self._keys[key]
            self._save()
            return False
        return True

    def revoke_key(self, key: str) -> bool:
        """Revoke a key."""
        if key in self._keys:
            del self._keys[key]
            self._save()
            logger.info(f"[relay-keys] Revoked key {key[:8]}...")
            return True
        return False

    def list_keys(self) -> list[dict]:
        """List all keys (masked) with metadata."""
        now = time.time()
        result = []
        for key, info in self._keys.items():
            age = now - info.get('created_at', 0)
            if age > self._ttl_seconds:
                continue
            result.append({
                'key_prefix': key[:8] + '...',
                'label': info.get('label', ''),
                'created_at': info.get('created_at'),
                'expires_in_hours': round((self._ttl_seconds - age) / 3600, 1),
            })
        return result


def create_key_api(key_manager: RelayKeyManager) -> list[Route]:
    """Create REST API routes for key management."""

    async def create_key(request: Request) -> JSONResponse:
        ct = request.headers.get('content-type', '')
        body = await request.json() if 'application/json' in ct else {}
        label = body.get('label', '')
        key = key_manager.create_key(label)
        return JSONResponse({'key': key, 'label': label}, status_code=201)

    async def list_keys(request: Request) -> JSONResponse:
        keys = key_manager.list_keys()
        return JSONResponse({'keys': keys})

    async def revoke_key(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({'error': 'Invalid JSON'}, status_code=400)
        key = body.get('key', '')
        if key_manager.revoke_key(key):
            return JSONResponse({'revoked': True})
        return JSONResponse({'revoked': False, 'error': 'Key not found'}, status_code=404)

    return [
        Route('/keys', list_keys, methods=['GET']),
        Route('/keys', create_key, methods=['POST']),
        Route('/keys/revoke', revoke_key, methods=['POST']),
    ]
