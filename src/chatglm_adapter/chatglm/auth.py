import asyncio
import base64
import binascii
import json
import time
from dataclasses import dataclass

import httpx

from ..config import Settings
from ..core.errors import AuthenticationError, ConfigurationError, UpstreamError
from ..security.secrets import atomic_write_secret, read_secret_file
from .headers import build_headers
from .signer import ChatGLMSigner


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float


def _jwt_expiry(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        value = payload.get("exp")
        return float(value) if value is not None else None
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError):
        return None


class AuthManager:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        signer: ChatGLMSigner,
        device_id: str,
    ):
        self._settings = settings
        self._client = client
        self._signer = signer
        self._device_id = device_id
        self._cache: _TokenCache | None = None
        self._lock = asyncio.Lock()

    @property
    def ready(self) -> bool:
        if not self._settings.chatglm_auth_refresh_url:
            return False
        try:
            read_secret_file(self._settings.chatglm_refresh_token_file)
        except ConfigurationError:
            return False
        return True

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            now = time.time()
            if (
                not force_refresh
                and self._cache
                and self._cache.expires_at > now + self._settings.auth_refresh_skew_seconds
            ):
                return self._cache.access_token
            return await self._refresh_locked()

    async def _refresh_locked(self) -> str:
        url = self._settings.chatglm_auth_refresh_url
        if not url:
            raise ConfigurationError("CHATGLM_AUTH_REFRESH_URL is not configured")
        refresh_token = read_secret_file(self._settings.chatglm_refresh_token_file)
        await self._signer.sync(self._client, self._settings.chatglm_time_sync_url)
        headers = build_headers(
            self._settings,
            self._signer,
            access_token=refresh_token,
            device_id=self._device_id,
            accept="application/json",
            content_type="application/json;charset=utf-8",
        )
        try:
            response = await self._client.post(url, headers=headers, json={})
        except httpx.HTTPError as exc:
            raise UpstreamError("ChatGLM token refresh request failed", retryable=True) from exc
        if response.status_code >= 400:
            raise AuthenticationError(f"ChatGLM token refresh rejected ({response.status_code})")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthenticationError("ChatGLM token refresh returned invalid JSON") from exc

        access_token = _find_token(payload, "access_token") or _find_token(payload, "token")
        if not access_token:
            raise AuthenticationError("ChatGLM token refresh response has no access token")
        rotated = _find_token(payload, "refresh_token")
        if rotated and rotated != refresh_token:
            atomic_write_secret(self._settings.chatglm_refresh_token_file, rotated)
        expires_at = _jwt_expiry(access_token) or (time.time() + 300)
        self._cache = _TokenCache(access_token=access_token, expires_at=expires_at)
        return access_token


def _find_token(payload: object, key: str) -> str | None:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        for nested in payload.values():
            found = _find_token(nested, key)
            if found:
                return found
    elif isinstance(payload, list):
        for nested in payload:
            found = _find_token(nested, key)
            if found:
                return found
    return None
