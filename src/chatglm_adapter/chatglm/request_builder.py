from typing import Any

from ..openai.schemas import ChatCompletionRequest, ContentPart, Message
from .models import ChatGLMRequest


class ChatGLMRequestBuilder:
    """Builds the smallest currently documented Web request shape.

    The field names are kept in one module so a new HAR can change the protocol
    without coupling the OpenAI API layer to it.
    """

    def __init__(self, upstream_model: str):
        self._upstream_model = upstream_model

    def build(self, request: ChatCompletionRequest, conversation_id: str) -> ChatGLMRequest:
        metadata = {
            "cogview": {"rm_label_watermark": True},
            "is_test": False,
            "input_question_type": "",
            "channel": "",
            "draft_id": "",
            "chat_mode": "deep_thinking",
            "selected_model": self._upstream_model,
            "is_networking": bool(request.web_search),
            "quote_log_id": "",
            "platform": "pc",
        }
        body: dict[str, Any] = {
            "assistant_id": "",
            "conversation_id": conversation_id,
            "project_id": "",
            "chat_type": "user_chat",
            "meta_data": metadata,
            "messages": [self._message(message) for message in request.messages],
        }
        return ChatGLMRequest(body=body)

    @staticmethod
    def _message(message: Message) -> dict[str, Any]:
        return {
            "role": message.role,
            "content": [
                {"type": "text", "text": part.text}
                for part in _text_parts(message.content)
            ],
        }


def _text_parts(content: str | list[ContentPart]) -> list[ContentPart]:
    if isinstance(content, str):
        return [ContentPart(type="text", text=content)]
    return [part for part in content if part.type == "text"]

