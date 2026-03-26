"""Thin wrapper around PyJWT for encoding / decoding JWTs."""

from __future__ import annotations

from typing import Any


class JWTDecodeError(Exception):
    """Raised when JWT decoding fails (bad signature, malformed, etc.)."""


class JWTExpiredError(JWTDecodeError):
    """Raised when the JWT has expired."""


def decode_jwt(
    token: str,
    secret: str,
    *,
    algorithm: str = "HS256",
    verify_exp: bool = True,
    issuer: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT, returning the raw payload dict.

    Raises :class:`JWTExpiredError` on expiry and :class:`JWTDecodeError` for
    all other validation failures.
    """
    import jwt  # PyJWT — lazy import

    options: dict[str, Any] = {}
    if not verify_exp:
        options["verify_exp"] = False

    kwargs: dict[str, Any] = {
        "algorithms": [algorithm],
        "options": options,
    }
    if issuer is not None:
        kwargs["issuer"] = issuer
    if audience is not None:
        kwargs["audience"] = audience

    try:
        return jwt.decode(token, secret, **kwargs)
    except jwt.ExpiredSignatureError as exc:
        raise JWTExpiredError(str(exc)) from exc
    except jwt.PyJWTError as exc:
        raise JWTDecodeError(str(exc)) from exc


def encode_jwt(
    payload: dict[str, Any],
    secret: str,
    *,
    algorithm: str = "HS256",
) -> str:
    """Encode *payload* into a signed JWT string."""
    import jwt  # PyJWT — lazy import

    return jwt.encode(payload, secret, algorithm=algorithm)
