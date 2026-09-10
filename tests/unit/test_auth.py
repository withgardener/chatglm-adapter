import httpx
import pytest

from chatglm_adapter.chatglm.auth import AuthManager
from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider
from chatglm_adapter.config import Settings
from chatglm_adapter.security.secrets import atomic_write_secret, read_secret_file


@pytest.mark.asyncio
async def test_auth_refresh_caches_and_rotates_refresh_token(tmp_path):
    refresh_file = tmp_path / "refresh-token"
    atomic_write_secret(refresh_file, "old-refresh")

    def handler(request: httpx.Request):
        if request.url.path == "/cur_ts":
            return httpx.Response(200, json={"result": {"timestamp_ms": 1700000000000}})
        assert request.url.path == "/refresh"
        assert request.read() == b"{}"
        assert request.headers["authorization"] == "Bearer old-refresh"
        assert request.headers["x-sign"]
        return httpx.Response(
            200,
            json={"data": {"access_token": "access-1", "refresh_token": "new-refresh"}},
        )

    settings = Settings(
        chatglm_auth_refresh_url="https://chatglm.test/refresh",
        chatglm_time_sync_url="https://chatglm.test/cur_ts",
        chatglm_sign_secret="secret",
        chatglm_refresh_token_file=refresh_file,
        auth_refresh_skew_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        signer = ChatGLMSigner("secret", TimestampProvider("unix_ms"))
        auth = AuthManager(settings, client, signer, "0" * 32)
        assert await auth.get_access_token() == "access-1"
        assert await auth.get_access_token() == "access-1"
    assert read_secret_file(refresh_file) == "new-refresh"
