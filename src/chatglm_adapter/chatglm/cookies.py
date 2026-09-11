from pathlib import Path

from ..core.errors import ConfigurationError
from ..security.secrets import atomic_write_secret, read_secret_file

REFRESH_TOKEN_COOKIE = "chatglm_refresh_token"
ACCESS_TOKEN_COOKIE = "chatglm_token"


def parse_cookie_header(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in header.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        name = name.strip()
        if name:
            cookies[name] = value.strip()
    return cookies


def serialize_cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


class CookieStore:
    """Full Cookie header imported from a logged-in ChatGLM Web session.

    The refresh token is read from the cookie string and kept current both in
    memory and on disk when the upstream rotates it.
    """

    def __init__(self, path: Path, cookies: dict[str, str]):
        self._path = path
        self._cookies = dict(cookies)

    @classmethod
    def load(cls, path: Path) -> "CookieStore":
        cookies = parse_cookie_header(read_secret_file(path))
        if not cookies.get(REFRESH_TOKEN_COOKIE):
            raise ConfigurationError(f"cookie file has no {REFRESH_TOKEN_COOKIE}: {path}")
        return cls(path, cookies)

    @property
    def refresh_token(self) -> str:
        return self._cookies[REFRESH_TOKEN_COOKIE]

    def header(self, *, access_token: str | None = None) -> str:
        cookies = dict(self._cookies)
        if access_token and ACCESS_TOKEN_COOKIE in cookies:
            cookies[ACCESS_TOKEN_COOKIE] = access_token
        return serialize_cookie_header(cookies)

    def rotate_refresh_token(self, rotated: str) -> None:
        self._cookies[REFRESH_TOKEN_COOKIE] = rotated
        atomic_write_secret(self._path, serialize_cookie_header(self._cookies))
