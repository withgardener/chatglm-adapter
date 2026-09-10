import secrets
from pathlib import Path

from ..security.secrets import atomic_write_secret, read_secret_file


def load_or_create_device_id(path: Path) -> str:
    if path.exists():
        return read_secret_file(path)
    device_id = secrets.token_hex(16)
    atomic_write_secret(path, device_id)
    return device_id

