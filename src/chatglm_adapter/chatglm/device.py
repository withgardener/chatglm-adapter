import secrets
from pathlib import Path

from ..config import Settings
from ..security.secrets import atomic_write_secret, read_secret_file
from .auth import jwt_claim


def load_or_create_device_id(path: Path) -> str:
    if path.exists():
        return read_secret_file(path)
    device_id = secrets.token_hex(16)
    atomic_write_secret(path, device_id)
    return device_id


def resolve_device_id(settings: Settings, refresh_token: str | None = None) -> str:
    """Prefer an explicit override, then the token's device_id claim, then a
    locally generated ID. ChatGLM binds tokens to the browser device, so a
    mismatch between X-Device-Id and the token claim can reject refreshes."""
    if settings.chatglm_device_id:
        return settings.chatglm_device_id
    if refresh_token:
        claim = jwt_claim(refresh_token, "device_id")
        if claim:
            return claim
    return load_or_create_device_id(settings.chatglm_device_id_file)
