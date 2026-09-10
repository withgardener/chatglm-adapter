import httpx
import pytest

from chatglm_adapter.chatglm.auth import AuthManager
from chatglm_adapter.config import Settings
from chatglm_adapter.security.secrets import atomic_write_secret, read_secret_file


@pytest.mark.asyncio
async def test_auth_refresh_caches_and_rotates_refresh_token(tmp_path):
    refresh_file = tmp_path / "refresh-token"
    atomic_write_secret(refresh_file, "old-refresh")

    def handler(request: httpx.Request):
        assert request.url.path == "/refresh"
        assert request.read() == b'{"refresh_token":"old-refresh"}'
        return httpx.Response(
            200,
            json={"data": {"access_token": "access-1", "refresh_token": "new-refresh"}},
        )

    settings = Settings(
        chatglm_auth_refresh_url="https://chatglm.test/refresh",
        chatglm_refresh_token_file=refresh_file,
        auth_refresh_skew_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        auth = AuthManager(settings, client)
        assert await auth.get_access_token() == "access-1"
        assert await auth.get_access_token() == "access-1"
    assert read_secret_file(refresh_file) == "new-refresh"

