from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatGLMConversation:
    conversation_id: str


@dataclass(frozen=True)
class ChatGLMRequest:
    body: dict[str, Any]

