import re
from typing import Any


_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_BEARER = re.compile(r"(?i)(Bearer\s+)[^\s,;]+")
_SECRET_KEYS = re.compile(
    r"(?i)^(authorization|cookie|access_token|refresh_token|chatglm_refresh_token|x-device-id)$"
)


def redact_text(value: str) -> str:
    value = _BEARER.sub(r"\1<REDACTED>", value)
    return _JWT.sub("<JWT_REDACTED>", value)


def redact(value: Any, *, key: str | None = None) -> Any:
    if key and _SECRET_KEYS.match(key):
        return "<REDACTED>"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value

