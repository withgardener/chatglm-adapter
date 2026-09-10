import asyncio
from collections.abc import AsyncIterator

import httpx

from ..config import Settings
from ..core.errors import UpstreamError
from ..core.retry import StreamState
from .auth import AuthManager
from .conversation import ConversationManager
from .headers import build_headers
from .request_builder import ChatGLMRequestBuilder
from .signer import ChatGLMSigner
from .sse_parser import RawSSEEvent, decode_stream


class ChatGLMClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        auth: AuthManager,
        signer: ChatGLMSigner,
        device_id: str,
        conversations: ConversationManager,
    ):
        self._settings = settings
        self._http = http_client
        self._auth = auth
        self._signer = signer
        self._device_id = device_id
        self._conversations = conversations

    async def stream(
        self,
        request,
        builder: ChatGLMRequestBuilder,
        *,
        request_id: str,
    ) -> AsyncIterator[RawSSEEvent]:
        state = StreamState()
        attempted_refresh = False
        attempts = 0
        while attempts < 2:
            attempts += 1
            token = await self._auth.get_access_token(force_refresh=attempted_refresh)
            base_headers = build_headers(
                self._settings,
                self._signer,
                access_token=token,
                device_id=self._device_id,
                request_id=request_id,
            )
            conversation = None
            try:
                conversation = await self._conversations.create(base_headers)
                body = builder.build(request, conversation.conversation_id).body
                async with self._http.stream(
                    "POST",
                    self._settings.chatglm_stream_url,
                    headers=base_headers,
                    json=body,
                    timeout=self._settings.upstream_request_timeout_seconds,
                ) as response:
                    if response.status_code == 401 and not state.started and not attempted_refresh:
                        attempted_refresh = True
                        continue
                    if response.status_code == 429 and not state.started and attempts == 1:
                        await asyncio.sleep(0.2)
                        continue
                    if response.status_code >= 400:
                        raise UpstreamError(
                            f"ChatGLM stream rejected ({response.status_code})",
                            status_code=response.status_code,
                            retryable=(response.status_code in {500, 502, 503, 504} and not state.started),
                        )
                    async for event in decode_stream(response.aiter_text()):
                        state.mark_emitted()
                        yield event
                    return
            except UpstreamError as exc:
                if not state.started and attempts < 2 and (exc.retryable or exc.status_code == 401):
                    if exc.status_code == 401:
                        attempted_refresh = True
                    continue
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if state.started or attempts >= 2:
                    raise UpstreamError("ChatGLM stream failed", retryable=False) from exc
                continue
            finally:
                if conversation is not None:
                    await self._conversations.cleanup(conversation, base_headers)
        raise UpstreamError("ChatGLM stream retry budget exhausted")
