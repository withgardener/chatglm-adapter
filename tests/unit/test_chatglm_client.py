import httpx
import pytest

from chatglm_adapter.chatglm.auth import AuthManager
from chatglm_adapter.chatglm.client import ChatGLMClient
from chatglm_adapter.chatglm.conversation import ConversationManager
from chatglm_adapter.chatglm.request_builder import ChatGLMRequestBuilder
from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider
from chatglm_adapter.config import Settings
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
