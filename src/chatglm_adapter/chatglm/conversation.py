import logging
from typing import Any

import httpx

from ..config import Settings
from ..core.errors import ConfigurationError, UpstreamError
from .models import ChatGLMConversation

logger = logging.getLogger(__name__)


class ConversationManager:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self._settings = settings
        self._client = client

    async def create(self, headers: dict[str, str]) -> ChatGLMConversation:
        if not self._settings.chatglm_conversation_create_url:
            raise ConfigurationError("CHATGLM_CONVERSATION_CREATE_URL is not configured")
        try:
            response = await self._client.post(
                self._settings.chatglm_conversation_create_url,
                headers=headers,
                json={},
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("ChatGLM conversation creation request failed", retryable=True) from exc
        if response.status_code >= 400:
            raise UpstreamError(
                "ChatGLM conversation creation failed",
                status_code=response.status_code,
                retryable=response.status_code in {429, 500, 502, 503, 504},
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamError("ChatGLM conversation response was not JSON") from exc
        conversation_id = _find_string(payload, "conversation_id") or _find_string(payload, "id")
        if not conversation_id:
            raise UpstreamError("ChatGLM conversation response has no conversation id")
        return ChatGLMConversation(conversation_id=conversation_id)

    async def cleanup(self, conversation: ChatGLMConversation, headers: dict[str, str]) -> None:
        if not self._settings.chatglm_conversation_delete_url:
            return
        try:
            await self._client.request(
                "DELETE",
                self._settings.chatglm_conversation_delete_url,
                headers=headers,
                json={"conversation_id": conversation.conversation_id},
            )
        except httpx.HTTPError:
            logger.warning("conversation cleanup failed", extra={"error_class": "network"})
        except Exception:
            logger.warning("conversation cleanup failed", extra={"error_class": "unknown"})


def _find_string(payload: Any, key: str) -> str | None:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        for nested in payload.values():
            found = _find_string(nested, key)
            if found:
                return found
    elif isinstance(payload, list):
        for nested in payload:
            found = _find_string(nested, key)
            if found:
                return found
    return None
