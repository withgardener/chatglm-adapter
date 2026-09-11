import asyncio

import httpx
import pytest

from chatglm_adapter.chatglm.auth import AuthManager
from chatglm_adapter.chatglm.client import ChatGLMClient, _retry_after_seconds
from chatglm_adapter.chatglm.conversation import ConversationManager
from chatglm_adapter.chatglm.request_builder import ChatGLMRequestBuilder
from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider
from chatglm_adapter.config import Settings
from chatglm_adapter.core.errors import UpstreamError
from chatglm_adapter.openai.schemas import ChatCompletionRequest
from chatglm_adapter.security.secrets import atomic_write_secret


@pytest.mark.asyncio
async def test_client_creates_streams_and_cleans_temporary_conversation(tmp_path):
    refresh_file = tmp_path / "refresh-token"
    atomic_write_secret(refresh_file, "refresh")
    calls: list[str] = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path == "/cur_ts":
            return httpx.Response(200, json={"result": {"timestamp_ms": 1700000000000}})
        if request.url.path == "/refresh":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path == "/stream":
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"status":"init","conversation_id":"conversation-1","parts":[]}\n\n'
                b'data: {"content":"ok"}\n\ndata: [DONE]\n\n',
            )
        if request.url.path == "/conversation/delete":
            assert request.read() == b'{"conversation_id":"conversation-1"}'
            return httpx.Response(204, request=request)
        raise AssertionError(request.url.path)

    settings = Settings(
        chatglm_stream_url="https://chatglm.test/stream",
        chatglm_auth_refresh_url="https://chatglm.test/refresh",
        chatglm_time_sync_url="https://chatglm.test/cur_ts",
        chatglm_conversation_delete_url="https://chatglm.test/conversation/delete",
        chatglm_sign_secret="secret",
        chatglm_refresh_token_file=refresh_file,
        auth_refresh_skew_seconds=0,
    )
    request = ChatCompletionRequest(
        model="chatglm-glm-5.3-flash",
        messages=[{"role": "user", "content": "hello"}],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        signer = ChatGLMSigner("secret", TimestampProvider("unix_ms"))
        auth = AuthManager(settings, http, signer, "0" * 32)
        client = ChatGLMClient(
            settings,
            http,
            auth,
            signer,
            "0" * 32,
            ConversationManager(settings, http),
        )
        events = [
            event
            async for event in client.stream(
                request,
                ChatGLMRequestBuilder("glm-5.3-flash"),
                request_id="request-1",
            )
        ]
    assert [event.data for event in events] == [
        '{"status":"init","conversation_id":"conversation-1","parts":[]}',
        '{"content":"ok"}',
        "[DONE]",
    ]
    assert calls == ["/cur_ts", "/refresh", "/stream", "/conversation/delete"]


def _make_client(tmp_path, handler):
    refresh_file = tmp_path / "refresh-token"
    atomic_write_secret(refresh_file, "refresh")
    settings = Settings(
        chatglm_stream_url="https://chatglm.test/stream",
        chatglm_auth_refresh_url="https://chatglm.test/refresh",
        chatglm_time_sync_url="https://chatglm.test/cur_ts",
        chatglm_sign_secret="secret",
        chatglm_refresh_token_file=refresh_file,
        auth_refresh_skew_seconds=0,
    )
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    signer = ChatGLMSigner("secret", TimestampProvider("unix_ms"))
    auth = AuthManager(settings, http, signer, "0" * 32)
    client = ChatGLMClient(
        settings,
        http,
        auth,
        signer,
        "0" * 32,
        ConversationManager(settings, http),
    )
    request = ChatCompletionRequest(
        model="chatglm-glm-5.3-flash",
        messages=[{"role": "user", "content": "hello"}],
    )
    return http, client, request


@pytest.mark.asyncio
async def test_429_without_retry_after_is_surfaced_without_retry(tmp_path):
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        if request.url.path == "/cur_ts":
            return httpx.Response(200, json={"result": {"timestamp_ms": 1}})
        if request.url.path == "/refresh":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path == "/stream":
            calls += 1
            return httpx.Response(429, json={"status": 10061, "message": "请求过于频繁"})
        raise AssertionError(request.url.path)

    http, client, request = _make_client(tmp_path, handler)
    async with http:
        with pytest.raises(UpstreamError) as excinfo:
            async for _ in client.stream(
                request, ChatGLMRequestBuilder("glm-5.3-flash"), request_id="r"
            ):
                pass
    assert excinfo.value.status_code == 429
    assert "请求过于频繁" in str(excinfo.value)
    assert calls == 1


@pytest.mark.asyncio
async def test_429_with_retry_after_waits_then_retries(tmp_path, monkeypatch):
    calls = 0
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request):
        nonlocal calls
        if request.url.path == "/cur_ts":
            return httpx.Response(200, json={"result": {"timestamp_ms": 1}})
        if request.url.path == "/refresh":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path == "/stream":
            calls += 1
            if calls == 1:
                return httpx.Response(429, headers={"Retry-After": "3"})
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"content":"ok"}\n\ndata: [DONE]\n\n',
            )
        raise AssertionError(request.url.path)

    http, client, request = _make_client(tmp_path, handler)
    async with http:
        events = [
            event
            async for event in client.stream(
                request, ChatGLMRequestBuilder("glm-5.3-flash"), request_id="r"
            )
        ]
    assert calls == 2
    assert sleeps == [3.0]
    assert [event.data for event in events] == ['{"content":"ok"}', "[DONE]"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3", 3.0), ("0.5", 0.5), (None, None), ("", None), ("0", None), ("60", None), ("soon", None)],
)
def test_retry_after_seconds_parsing(value, expected):
    assert _retry_after_seconds(value) == expected
