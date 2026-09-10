import asyncio
import hashlib
import secrets
import time
from typing import Any

import httpx

from ..core.errors import ConfigurationError


class TimestampProvider:
    def __init__(self, fmt: str = "unix_ms"):
        self._format = fmt
        self._offset_ms = 0.0
        self._sync_lock = asyncio.Lock()
        self._synced = False

    def now(self) -> str:
        raw_ms = int(time.time() * 1000 + self._offset_ms)
        if self._format == "unix_ms":
            return str(raw_ms)
        if self._format == "unix_s":
            return str(raw_ms // 1000)
        if self._format == "chatglm_checksum":
            raw = str(raw_ms)
            if len(raw) < 2:
                raise ConfigurationError("ChatGLM timestamp must contain at least two digits")
            digits = [int(digit) for digit in raw]
            replacement = (sum(digits) - digits[-2]) % 10
            return f"{raw[:-2]}{replacement}{raw[-1]}"
        raise ConfigurationError(f"unsupported timestamp format: {self._format}")

    async def sync(self, client: httpx.AsyncClient, url: str) -> None:
        """Best-effort replica of the web client's midpoint clock synchronisation."""
        if not url or self._synced:
            return
        async with self._sync_lock:
            if not url or self._synced:
                return
            started_mono = time.perf_counter()
            try:
                response = await client.get(url, timeout=5.0)
                response.raise_for_status()
                payload: Any = response.json()
                server_ms = payload["result"]["timestamp_ms"]
                if not isinstance(server_ms, (int, float)):
                    raise ValueError("timestamp_ms is not numeric")
                elapsed_ms = (time.perf_counter() - started_mono) * 1000
                self._offset_ms = float(server_ms) + elapsed_ms / 2 - time.time() * 1000
                self._synced = True
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                # The browser also continues with local time when this probe fails.
                return


class ChatGLMSigner:
    def __init__(self, secret: str, timestamp_provider: TimestampProvider):
        if not secret:
            raise ConfigurationError("CHATGLM_SIGN_SECRET is required")
        self._secret = secret
        self._timestamp_provider = timestamp_provider

    def sign(self, timestamp: str, nonce: str) -> str:
        material = f"{timestamp}-{nonce}-{self._secret}".encode("utf-8")
        return hashlib.md5(material).hexdigest()

    async def sync(self, client: httpx.AsyncClient, url: str) -> None:
        await self._timestamp_provider.sync(client, url)

    def new_headers(self, *, nonce: str | None = None) -> dict[str, str]:
        timestamp = self._timestamp_provider.now()
        resolved_nonce = nonce or secrets.token_hex(16)
        return {
            "X-Timestamp": timestamp,
            "X-Nonce": resolved_nonce,
            "X-Sign": self.sign(timestamp, resolved_nonce),
        }
