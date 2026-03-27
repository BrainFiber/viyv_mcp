"""``python -m viyv_mcp`` entry-point for CLI commands."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

from viyv_mcp import __version__


def _parse_duration(value: str) -> int:
    """Convert a human-readable duration string to seconds.

    Accepts: ``30m``, ``24h``, ``7d``.
    """
    m = re.fullmatch(r"(\d+)\s*([mhd])", value.strip().lower())
    if not m:
        raise argparse.ArgumentTypeError(
            f"Invalid duration: {value!r}. Use e.g. 30m, 24h, 7d."
        )
    amount, unit = int(m.group(1)), m.group(2)
    multiplier = {"m": 60, "h": 3600, "d": 86400}
    return amount * multiplier[unit]


def cmd_generate_jwt(args: argparse.Namespace) -> None:
    """Generate a signed JWT for agent authentication."""
    from viyv_mcp.app.security.infrastructure.jwt_codec import encode_jwt

    secret = args.secret or os.environ.get("VIYV_MCP_JWT_SECRET", "")
    if not secret:
        print(
            "Error: --secret or VIYV_MCP_JWT_SECRET environment variable is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    now = int(time.time())
    expires_seconds = _parse_duration(args.expires)

    payload = {
        "sub": args.sub,
        "namespace": args.namespace,
        "iat": now,
        "exp": now + expires_seconds,
    }
    if args.clearance is not None:
        payload["clearance"] = args.clearance
    if args.trust:
        payload["trust"] = args.trust

    token = encode_jwt(payload, secret, algorithm=args.algorithm)
    print(token)


def cmd_serve(args: argparse.Namespace) -> None:
    """Start MCP server with bridge configs (no project directory needed)."""
    import asyncio
    from viyv_mcp import ViyvMCP

    bridge_config = os.path.abspath(args.bridges) if args.bridges else None
    if bridge_config and not os.path.exists(bridge_config):
        print(f"Error: bridge config not found: {bridge_config}", file=sys.stderr)
        sys.exit(1)

    app = ViyvMCP(
        server_name=args.name,
        stateless_http=True if args.http else None,
        bridge_config=bridge_config,
    )

    if args.http:
        import uvicorn
        uvicorn.run(
            app.get_app(),
            host=args.host,
            port=args.port,
            log_level="info",
        )
    else:
        asyncio.run(app.run_stdio_async())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m viyv_mcp",
        description="viyv_mcp CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # --- generate-jwt -------------------------------------------------- #
    p_jwt = subparsers.add_parser(
        "generate-jwt",
        help="Generate a signed JWT for agent authentication",
    )
    p_jwt.add_argument("--sub", required=True, help="Agent name (JWT sub claim)")
    p_jwt.add_argument("--clearance", type=int, default=None,
                        help="Security clearance level (integer, 0=highest; omit for lowest)")
    p_jwt.add_argument("--namespace", required=True, help="Agent namespace")
    p_jwt.add_argument(
        "--trust", action="append", default=[], help="Additional trusted namespace (repeatable)"
    )
    p_jwt.add_argument("--expires", default="24h", help="Token lifetime (e.g. 30m, 24h, 7d)")
    p_jwt.add_argument("--secret", default="", help="JWT signing secret (or set VIYV_MCP_JWT_SECRET)")
    p_jwt.add_argument("--algorithm", default="HS256", help="JWT algorithm (default: HS256)")

    # --- serve --------------------------------------------------------- #
    p_serve = subparsers.add_parser(
        "serve",
        help="Start MCP server (stdio or HTTP, no project dir needed)",
    )
    p_serve.add_argument(
        "--bridges", required=True,
        help="Path to bridge config JSON file or directory of *.json files",
    )
    p_serve.add_argument("--name", default="viyv-bridge", help="Server name (default: viyv-bridge)")
    p_serve.add_argument("--http", action="store_true", help="Use HTTP transport instead of stdio")
    p_serve.add_argument("--host", default="0.0.0.0", help="HTTP host (default: 0.0.0.0)")
    p_serve.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")

    args = parser.parse_args()

    if args.command == "generate-jwt":
        cmd_generate_jwt(args)
    elif args.command == "serve":
        cmd_serve(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
