import os
import secrets
from pathlib import Path

from ..core.errors import ConfigurationError


def read_secret_file(path: Path) -> str:
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError as exc:
        raise ConfigurationError(f"secret file not found: {path}") from exc
    # Windows does not expose NTFS ACLs through st_mode. Production containers
    # run on Linux, where this check enforces the documented 0600 contract.
    if os.name != "nt" and mode & 0o077:
        raise ConfigurationError(f"secret file must not be group/world readable: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ConfigurationError(f"secret file is empty: {path}")
    return value


def atomic_write_secret(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value.rstrip() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
