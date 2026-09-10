import json
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..core.events import (
    Error,
    Finish,
    NormalizedEvent,
    ReasoningDelta,
    TextDelta,
    Unknown,
    Usage,
)


@dataclass
class CompletionAccumulator:
    content: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Usage = field(default_factory=Usage)

    def consume(self, event: NormalizedEvent) -> None:
        if isinstance(event, TextDelta):
            self.content.append(event.text)
        elif isinstance(event, ReasoningDelta):
            self.reasoning.append(event.text)
        elif isinstance(event, Finish):
            self.finish_reason = event.reason
        elif isinstance(event, Usage):
            self.usage = event

    def message(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(self.content),
        }
        if self.reasoning:
            result["reasoning_content"] = "".join(self.reasoning)
        return result


class OpenAIEncoder:
    def __init__(self, model: str):
        self.model = model
        self.completion_id = f"chatcmpl-{uuid4().hex}"
        self.created = int(time.time())

    def role_chunk(self) -> str:
        return self._sse(
            {
                "id": self.completion_id,
                "object": "chat.completion.chunk",
                "created": self.created,
                "model": self.model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
        )

    def event(self, event: NormalizedEvent, accumulator: CompletionAccumulator) -> str | None:
        accumulator.consume(event)
        delta: dict[str, Any] = {}
        finish_reason = None
        if isinstance(event, TextDelta):
            delta["content"] = event.text
        elif isinstance(event, ReasoningDelta):
            delta["reasoning_content"] = event.text
        elif isinstance(event, Finish):
            finish_reason = event.reason
        elif isinstance(event, Error):
            return self._sse({"error": {"type": event.code, "message": event.message}})
        elif isinstance(event, Unknown):
            return ": unknown_upstream_event\n\n"
        else:
            return None
        return self._sse(
            {
                "id": self.completion_id,
                "object": "chat.completion.chunk",
                "created": self.created,
                "model": self.model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
            }
        )

    def done(self) -> str:
        return "data: [DONE]\n\n"

    def non_stream(self, accumulator: CompletionAccumulator) -> dict[str, Any]:
        usage = accumulator.usage
        return {
            "id": self.completion_id,
            "object": "chat.completion",
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": accumulator.message(),
                    "finish_reason": accumulator.finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
        }

    @staticmethod
    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"

