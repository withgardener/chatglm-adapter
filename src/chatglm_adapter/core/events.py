from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ReasoningDelta:
    text: str


@dataclass(frozen=True)
class SearchEvent:
    payload: dict[str, Any]


@dataclass(frozen=True)
class ToolEvent:
    payload: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class Finish:
    reason: str = "stop"


@dataclass(frozen=True)
class Error:
    message: str
    code: str = "upstream_error"


@dataclass(frozen=True)
class Unknown:
    event: str | None
    payload_shape: Any


NormalizedEvent = (
    TextDelta | ReasoningDelta | SearchEvent | ToolEvent | Usage | Finish | Error | Unknown
)

