from chatglm_adapter.chatglm.sse_parser import RawSSEEvent, SSEDecoder, normalize
from chatglm_adapter.core.events import Finish, ReasoningDelta, TextDelta, Unknown


def test_decoder_handles_split_chunks_and_crlf():
    decoder = SSEDecoder()
    assert decoder.feed('event: message\r\ndata: {"content":"你') == []
    events = decoder.feed('好"}\r\n\r\n')
    assert events == [RawSSEEvent("message", '{"content":"你好"}')]


def test_normalize_text_reasoning_and_done():
    assert normalize(RawSSEEvent("message", '{"delta":{"content":"hi"}}')) == [TextDelta("hi")]
    assert normalize(RawSSEEvent("message", '{"reasoning_content":"thinking"}')) == [
        ReasoningDelta("thinking")
    ]
    assert normalize(RawSSEEvent(None, "[DONE]")) == [Finish()]


def test_unknown_event_is_explicit_and_does_not_keep_text():
    result = normalize(RawSSEEvent("new_event", '{"new_field":"secret"}'))
    assert isinstance(result[0], Unknown)
    assert result[0].payload_shape == {"new_field": "string"}


def test_normalize_current_chatglm_parts_and_finish_status():
    raw = RawSSEEvent(
        None,
        '{"status":"finish","conversation_id":"conv-1",'
        '"parts":[{"answer_type":"think","text":"先想"},'
        '{"answer_type":"text","text":"答案","status":"finish"}]}',
    )
    assert normalize(raw) == [ReasoningDelta("先想"), TextDelta("答案"), Finish()]
