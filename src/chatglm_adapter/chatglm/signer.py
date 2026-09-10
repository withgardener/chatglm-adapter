import hashlib
import secrets
import time

from ..core.errors import ConfigurationError


class TimestampProvider:
    def __init__(self, fmt: str = "unix_ms"):
        self._format = fmt

    def now(self) -> str:
        if self._format == "unix_ms":
            return str(int(time.time() * 1000))
        if self._format == "unix_s":
            return str(int(time.time()))
        raise ConfigurationError(f"unsupported timestamp format: {self._format}")


class ChatGLMSigner:
    def __init__(self, secret: str, timestamp_provider: TimestampProvider):
        if not secret:
            raise ConfigurationError("CHATGLM_SIGN_SECRET is required")
        self._secret = secret
        self._timestamp_provider = timestamp_provider

    def sign(self, timestamp: str, nonce: str) -> str:
        material = f"{timestamp}-{nonce}-{self._secret}".encode("utf-8")
        return hashlib.md5(material).hexdigest()

    def new_headers(self, *, nonce: str | None = None) -> dict[str, str]:
        timestamp = self._timestamp_provider.now()
        resolved_nonce = nonce or secrets.token_hex(16)
        return {
            "X-Timestamp": timestamp,
            "X-Nonce": resolved_nonce,
            "X-Sign": self.sign(timestamp, resolved_nonce),
        }

