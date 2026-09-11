import base64

import httpx
import pytest

from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider
from chatglm_adapter.chatglm.upload import FileUploader, decode_data_url
from chatglm_adapter.config import Settings
from chatglm_adapter.core.errors import UnsupportedFeatureError, UpstreamError

_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


class _StubAuth:
    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        return "access-1"

    def cookie_header(self, access_token=None) -> str | None:
        return None


def _uploader(handler, **overrides) -> FileUploader:
    settings = Settings(
        adapter_internal_api_key="k",
        chatglm_sign_secret="secret",
        **overrides,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    signer = ChatGLMSigner("secret", TimestampProvider("unix_ms"))
    return FileUploader(settings, client, _StubAuth(), signer, "0" * 32)


def test_decode_data_url_happy_path():
    payload, name, mime = decode_data_url(f"data:image/png;base64,{_PNG}", max_bytes=1024)
    assert payload == b"\x89PNG\r\n\x1a\nfake"
    assert name == "image.png"
    assert mime == "image/png"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/a.png",
        "data:text/html;base64,PGI+",
        "data:image/png;base64,!!!",
        "data:image/png;base64,",
        "data:image/tiff;base64,AA==",
    ],
)
def test_decode_data_url_rejects_unsupported_inputs(url):
    with pytest.raises(UnsupportedFeatureError):
        decode_data_url(url, max_bytes=1024)


def test_decode_data_url_enforces_size_limit():
    with pytest.raises(UnsupportedFeatureError):
        decode_data_url(f"data:image/png;base64,{_PNG}", max_bytes=4)


@pytest.mark.asyncio
async def test_upload_posts_multipart_and_maps_response():
    def handler(request: httpx.Request):
        assert request.url.path == "/chatglm/productivity-api/file/chat_upload"
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert request.headers["authorization"] == "Bearer access-1"
        body = request.read()
        assert b'name="from"' in body and b"chat" in body
        assert b'name="assistant_id"' in body
        assert b'name="file"; filename="image.png"' in body
        return httpx.Response(
            200,
            json={
                "status": 0,
                "result": {
                    "file_id": "fid-1",
                    "file_url": "https://t1.chatglm.cn/file/fid-1.jpg?sign=x",
                    "file_name": "image.png",
                    "file_size": 343296,
                },
            },
        )

    uploader = _uploader(handler)
    uploaded = await uploader.upload(f"data:image/png;base64,{_PNG}")
    assert uploaded.file_id == "fid-1"
    assert uploaded.image_url.startswith("https://t1.chatglm.cn/file/")
    assert uploaded.file_size == 343296


@pytest.mark.asyncio
async def test_upload_rejection_raises_upstream_error():
    def handler(request: httpx.Request):
        return httpx.Response(413, json={"message": "too large"})

    uploader = _uploader(handler)
    with pytest.raises(UpstreamError):
        await uploader.upload(f"data:image/png;base64,{_PNG}")


@pytest.mark.asyncio
async def test_upload_retries_once_with_fresh_token_on_401():
    calls = 0

    class RefreshTrackingAuth(_StubAuth):
        def __init__(self):
            self.force_refreshes: list[bool] = []

        async def get_access_token(self, *, force_refresh: bool = False) -> str:
            self.force_refreshes.append(force_refresh)
            return "access-2" if force_refresh else "access-1"

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if request.headers["authorization"] == "Bearer access-1":
            return httpx.Response(401, json={"message": "expired"})
        return httpx.Response(
            200,
            json={
                "status": 0,
                "result": {
                    "file_id": "fid-2",
                    "file_url": "https://t1.chatglm.cn/file/fid-2.jpg",
                    "file_name": "image.png",
                    "file_size": 10,
                },
            },
        )

    settings = Settings(adapter_internal_api_key="k", chatglm_sign_secret="secret")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    signer = ChatGLMSigner("secret", TimestampProvider("unix_ms"))
    auth = RefreshTrackingAuth()
    uploader = FileUploader(settings, client, auth, signer, "0" * 32)
    uploaded = await uploader.upload(f"data:image/png;base64,{_PNG}")
    assert uploaded.file_id == "fid-2"
    assert calls == 2
    assert auth.force_refreshes == [False, True]


@pytest.mark.asyncio
async def test_upload_rejection_includes_redacted_body_excerpt():
    leaked = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5Jc"

    def handler(request: httpx.Request):
        return httpx.Response(429, text=f'{{"message":"quota exceeded","token":"{leaked}"}}')

    uploader = _uploader(handler)
    with pytest.raises(UpstreamError) as excinfo:
        await uploader.upload(f"data:image/png;base64,{_PNG}")
    assert "quota exceeded" in str(excinfo.value)
    assert leaked not in str(excinfo.value)
    assert "<JWT_REDACTED>" in str(excinfo.value)
