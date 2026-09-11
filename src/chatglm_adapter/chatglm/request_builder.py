from typing import Any

from ..openai.schemas import ChatCompletionRequest, Message
from .models import ChatGLMRequest
from .upload import UploadedImage


class ChatGLMRequestBuilder:
    """Builds the smallest currently documented Web request shape.

    The field names are kept in one module so a new HAR can change the protocol
    without coupling the OpenAI API layer to it.
    """

    def __init__(self, upstream_model: str, assistant_id: str = "65940acff94777010aa6b796"):
        self._upstream_model = upstream_model
        self._assistant_id = assistant_id

    def build(
        self,
        request: ChatCompletionRequest,
        conversation_id: str,
        images: dict[tuple[int, int], UploadedImage] | None = None,
    ) -> ChatGLMRequest:
        metadata = {
            "cogview": {"rm_label_watermark": True},
            "is_test": False,
            "input_question_type": "xxxx",
            "channel": "",
            "draft_id": "",
            "chat_mode": _chat_mode(request.reasoning_effort),
            "selected_model": self._upstream_model,
            "is_networking": bool(request.web_search),
            "quote_log_id": "",
            "platform": "pc",
        }
        body: dict[str, Any] = {
            "assistant_id": self._assistant_id,
            "conversation_id": conversation_id,
            "project_id": "",
            "chat_type": "user_chat",
            "meta_data": metadata,
            "messages": [
                self._message(message, message_index, images or {})
                for message_index, message in enumerate(request.messages)
            ],
        }
        return ChatGLMRequest(body=body)

    @staticmethod
    def _message(
        message: Message,
        message_index: int,
        images: dict[tuple[int, int], UploadedImage],
    ) -> dict[str, Any]:
        if isinstance(message.content, str):
            return {
                "role": message.role,
                "content": [{"type": "text", "text": message.content}],
            }
        parts: list[dict[str, Any]] = []
        image_order = 0
        for part_index, part in enumerate(message.content):
            if part.type == "text":
                if part.text:
                    parts.append({"type": "text", "text": part.text})
                continue
            uploaded = images.get((message_index, part_index))
            if uploaded is None:
                raise ValueError("image part was not uploaded")
            parts.append(
                {
                    "type": "image",
                    "image": [
                        {
                            "file_name": uploaded.file_name,
                            "file_id": uploaded.file_id,
                            "image_url": uploaded.image_url,
                            "file_size": uploaded.file_size,
                            "order": image_order,
                            "width": 0,
                            "height": 0,
                        }
                    ],
                }
            )
            image_order += 1
        return {"role": message.role, "content": parts}


def _chat_mode(reasoning_effort: str | None) -> str:
    # The web UI's current effort selector maps its three levels to these
    # private values; reasoning_effort itself is not an upstream field.
    return {
        None: "deep_thinking",
        "low": "",
        "high": "thinking",
        "max": "deep_thinking",
    }[reasoning_effort]
