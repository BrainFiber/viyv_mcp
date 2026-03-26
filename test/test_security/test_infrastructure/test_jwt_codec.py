"""Tests for JWT encode / decode."""

import time

import pytest

from viyv_mcp.app.security.infrastructure.jwt_codec import (
    JWTDecodeError,
    JWTExpiredError,
    decode_jwt,
    encode_jwt,
)

SECRET = "a-test-secret-that-is-at-least-32-bytes-long!"


def _make_token(**overrides):
    payload = {
        "sub": "agent-1",
        "clearance": "internal",
        "namespace": "hr",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    payload.update(overrides)
    return encode_jwt(payload, SECRET)


def test_roundtrip():
    token = _make_token(trust=["common"])
    payload = decode_jwt(token, SECRET)
    assert payload["sub"] == "agent-1"
    assert payload["trust"] == ["common"]


def test_bad_signature():
    token = _make_token()
    with pytest.raises(JWTDecodeError):
        decode_jwt(token, "wrong-secret-that-is-definitely-wrong!!")


def test_expired_token():
    token = _make_token(exp=int(time.time()) - 10)
    with pytest.raises(JWTExpiredError):
        decode_jwt(token, SECRET)


def test_skip_exp_verification():
    token = _make_token(exp=int(time.time()) - 10)
    payload = decode_jwt(token, SECRET, verify_exp=False)
    assert payload["sub"] == "agent-1"


def test_malformed_token():
    with pytest.raises(JWTDecodeError):
        decode_jwt("not.a.jwt.token", SECRET)


def test_issuer_validation():
    token = _make_token(iss="my-server")
    payload = decode_jwt(token, SECRET, issuer="my-server")
    assert payload["iss"] == "my-server"


def test_issuer_mismatch():
    token = _make_token(iss="my-server")
    with pytest.raises(JWTDecodeError):
        decode_jwt(token, SECRET, issuer="wrong-server")


def test_audience_validation():
    token = _make_token(aud="viyv-mcp")
    payload = decode_jwt(token, SECRET, audience="viyv-mcp")
    assert payload["aud"] == "viyv-mcp"


def test_audience_mismatch():
    token = _make_token(aud="viyv-mcp")
    with pytest.raises(JWTDecodeError):
        decode_jwt(token, SECRET, audience="other-service")
