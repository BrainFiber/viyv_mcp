"""``python -m viyv_mcp`` entry-point for security / admin CLI commands."""

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
        "clearance": args.clearance,
        "namespace": args.namespace,
        "iat": now,
        "exp": now + expires_seconds,
    }
    if args.trust:
        payload["trust"] = args.trust

    token = encode_jwt(payload, secret, algorithm=args.algorithm)
    print(token)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m viyv_mcp",
        description="viyv_mcp CLI — security & admin commands",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # --- generate-jwt -------------------------------------------------- #
    p_jwt = subparsers.add_parser(
        "generate-jwt",
        help="Generate a signed JWT for agent authentication",
    )
    p_jwt.add_argument("--sub", required=True, help="Agent name (JWT sub claim)")
    p_jwt.add_argument("--clearance", required=True, help="Security clearance level")
    p_jwt.add_argument("--namespace", required=True, help="Agent namespace")
    p_jwt.add_argument(
        "--trust", action="append", default=[], help="Additional trusted namespace (repeatable)"
    )
    p_jwt.add_argument("--expires", default="24h", help="Token lifetime (e.g. 30m, 24h, 7d)")
    p_jwt.add_argument("--secret", default="", help="JWT signing secret (or set VIYV_MCP_JWT_SECRET)")
    p_jwt.add_argument("--algorithm", default="HS256", help="JWT algorithm (default: HS256)")

    args = parser.parse_args()

    if args.command == "generate-jwt":
        cmd_generate_jwt(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
