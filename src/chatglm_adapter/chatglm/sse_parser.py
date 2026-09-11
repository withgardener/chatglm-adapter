import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from ..core.events import (
    Error,
    Finish,
    NormalizedEvent,
    ReasoningDelta,
    SearchEvent,
    TextDelta,
    ToolEvent,
    Unknown,
    Usage,
)


@dataclass(frozen=True)
class RawSSEEvent:
    event: str | None
    data: str


class SSEDecoder:
    def __init__(self):
        self._buffer = ""
        self._event: str | None = None
        self._data: list[str] = []

    def feed(self, text: str) -> list[RawSSEEvent]:
        self._buffer += text
        events: list[RawSSEEvent] = []
        while True:
            newline = self._buffer.find("\n")
            if newline < 0:
                break
            line, self._buffer = self._buffer[:newline], self._buffer[newline + 1 :]
            if line.endswith("\r"):
                line = line[:-1]
            self._consume_line(line, events)
        return events

    def finish(self) -> list[RawSSEEvent]:
        if self._buffer:
            self._consume_line(self._buffer, [])
            self._buffer = ""
        events: list[RawSSEEvent] = []
        self._dispatch(events)
        return events

    def _consume_line(self, line: str, events: list[RawSSEEvent]) -> None:
        if not line:
            self._dispatch(events)
        elif line.startswith(":"):
            return
        elif line.startswith("event:"):
            self._event = line[6:].lstrip(" ")
        elif line.startswith("data:"):
            self._data.append(line[5:].lstrip(" "))

    def _dispatch(self, events: list[RawSSEEvent]) -> None:
        if self._data:
            events.append(RawSSEEvent(event=self._event, data="\n".join(self._data)))
        self._event = None
        self._data = []


async def decode_stream(chunks: AsyncIterator[str]) -> AsyncIterator[RawSSEEvent]:
    decoder = SSEDecoder()
    async for chunk in chunks:
        for event in decoder.feed(chunk):
            yield event
    for event in decoder.finish():
        yield event


def normalize(raw: RawSSEEvent) -> list[NormalizedEvent]:
    if raw.data.strip() == "[DONE]":
        return [Finish()]
    try:
        payload = json.loads(raw.data)
    except json.JSONDecodeError:
        return [Unknown(event=raw.event, payload_shape="invalid_json")]
    if not isinstance(payload, (dict, list)):
        return [Unknown(event=raw.event, payload_shape=_shape(payload))]

    event_name = (raw.event or "").lower()
    status = str(payload.get("status", "")).lower() if isinstance(payload, dict) else ""
    if "error" in event_name or status in {"error", "failed"} or _has_key(payload, "error"):
        message = _first_string(payload, ("message", "error", "msg")) or "upstream error"
        return [Error(message=message)]

    # Current content frames carry a top-level "tool_calls": [] even for plain
    # text answers, so parts must be normalized before the tool/search checks,
    # and those checks must require a truthy value rather than key presence.
    if isinstance(payload, dict) and isinstance(payload.get("parts"), list):
        if not payload["parts"]:
            # Known lifecycle frame (init/processing) with no content yet.
            last_error = payload.get("last_error")
            if isinstance(last_error, dict) and last_error:
                message = _first_string(last_error, ("message", "msg")) or "upstream error"
                return [Error(message=message)]
            return []
        result: list[NormalizedEvent] = []
        for part in payload["parts"]:
            result.extend(_normalize_part(part))
        if status == "finish" and not any(isinstance(event, Finish) for event in result):
            result.append(Finish())
        if result:
            return result

    if "search" in event_name or _has_truthy_key(payload, "search_results"):
        return [SearchEvent(payload=_as_dict(payload))]
    if "tool" in event_name or _has_truthy_key(payload, "tool_calls"):
        return [ToolEvent(payload=_as_dict(payload))]

    result: list[NormalizedEvent] = []
    reasoning = _first_string(payload, ("reasoning_content", "reasoning", "thinking"))
    if reasoning:
        result.append(ReasoningDelta(reasoning))
    text = _first_string(payload, ("content", "text", "answer"))
    if text:
        result.append(TextDelta(text))
    usage = _usage(payload)
    if usage:
        result.append(usage)
    finish_reason = _first_string(payload, ("finish_reason", "finish", "stop_reason"))
    if finish_reason:
        result.append(Finish(finish_reason))
    if result:
        return result
    if event_name in {"done", "finish", "completed", "complete"}:
        return [Finish()]
    return [Unknown(event=raw.event, payload_shape=_shape(payload))]


class StreamNormalizer:
    """Stateful per-request normalizer.

    Current ChatGLM content frames carry cumulative per-part snapshots rather
    than incremental deltas, so text channels must be diffed against what has
    already been emitted; incremental senders still pass through unchanged.
    """

    def __init__(self):
        self._emitted: dict[str, str] = {}

    def normalize(self, raw: RawSSEEvent) -> list[NormalizedEvent]:
        events = normalize(raw)
        return [event for event in (self._dedupe(event) for event in events) if event]

    def _dedupe(self, event: NormalizedEvent) -> NormalizedEvent | None:
        if isinstance(event, TextDelta):
            return self._diff("text", event, event.text)
        if isinstance(event, ReasoningDelta):
            return self._diff("reasoning", event, event.text)
        return event

    def _diff(self, channel: str, event: NormalizedEvent, text: str) -> NormalizedEvent | None:
        if not text:
            return None
        emitted = self._emitted.get(channel, "")
        if emitted and text == emitted:
            return None
        if emitted and text.startswith(emitted):
            self._emitted[channel] = text
            if isinstance(event, TextDelta):
                return TextDelta(text[len(emitted):])
            return ReasoningDelta(text[len(emitted):])
        self._emitted[channel] = emitted + text
        return event


def _normalize_part(part: object) -> list[NormalizedEvent]:
    if not isinstance(part, dict):
        return [Unknown(event=None, payload_shape=_shape(part))]

    # Current shape (2026-09-11 HAR): part.content is a list of typed items,
    # each carrying an incremental fragment.
    content = part.get("content")
    if isinstance(content, list):
        result: list[NormalizedEvent] = []
        for item in content:
            result.extend(_normalize_content_item(item))
        return result

    # Legacy flat shape (2026-09-10 HAR): text lives on the part itself.
    answer_type = str(
        part.get("answer_type")
        or part.get("type")
        or (part.get("meta_data") or {}).get("answer_type", "")
    ).lower()
    if answer_type in {"browser_result", "quote_result", "search", "search_result"}:
        return [SearchEvent(payload=part)]
    if answer_type in {"tool_calls", "tool_call", "function_call", "function_result", "tool_result"}:
        return [ToolEvent(payload=part)]
    if answer_type in {"think", "thinking", "reasoning", "advanced_thinking"}:
        text = _first_string(part, ("text", "content", "reasoning_content"))
        return [ReasoningDelta(text)] if text else []

    text = _first_string(part, ("text", "content", "answer"))
    # Part-level "finish" only marks that part as complete; it must not end the
    # OpenAI stream. Terminal Finish comes from the top-level status or [DONE].
    return [TextDelta(text)] if text else []


def _normalize_content_item(item: object) -> list[NormalizedEvent]:
    if not isinstance(item, dict):
        return [Unknown(event=None, payload_shape=_shape(item))]
    item_type = str(item.get("type", "")).lower()
    if item_type == "think":
        text = item.get("think")
        return [ReasoningDelta(text)] if isinstance(text, str) and text else []
    if item_type == "text" or (not item_type and isinstance(item.get("text"), str)):
        text = item.get("text")
        return [TextDelta(text)] if isinstance(text, str) and text else []
    if item_type in {"tool_calls", "tool_result"}:
        return [ToolEvent(payload=item)]
    return [Unknown(event=None, payload_shape=_shape(item))]


def _as_dict(payload: object) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {"items": payload}


def _has_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_has_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_has_key(v, key) for v in value)
    return False


def _has_truthy_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        if key in value and value[key]:
            return True
        return any(_has_truthy_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_has_truthy_key(v, key) for v in value)
    return False


def _first_string(value: object, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, dict):
        for key in keys:
            found = value.get(key)
            if isinstance(found, str) and found:
                return found
        for nested in value.values():
            found = _first_string(nested, keys)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _first_string(nested, keys)
            if found:
                return found
    return None


def _usage(value: object) -> Usage | None:
    if isinstance(value, dict):
        candidate = value.get("usage")
        if isinstance(candidate, dict):
            prompt = _int(candidate, "prompt_tokens")
            completion = _int(candidate, "completion_tokens")
            total = _int(candidate, "total_tokens")
            return Usage(prompt, completion, total)
        for nested in value.values():
            found = _usage(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _usage(nested)
            if found:
                return found
    return None


def _int(value: dict[str, Any], key: str) -> int:
    try:
        return int(value.get(key, 0))
    except (TypeError, ValueError):
        return 0


def _shape(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): _shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return {"list": len(value), "item": _shape(value[0]) if value else None}
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    return type(value).__name__
