from chatglm_adapter.chatglm.sse_parser import (
    RawSSEEvent,
    SSEDecoder,
    StreamNormalizer,
    normalize,
)
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


def test_content_frame_with_empty_tool_calls_is_not_a_tool_event():
    # Live probe 2026-09-11: every current content frame carries a top-level
    # "tool_calls": [], which must not shadow the parts payload.
    raw = RawSSEEvent(
        None,
        '{"id":"msg-1","conversation_id":"conv-1","status":"processing",'
        '"parts":[{"type":"content","content":[{"type":"text","text":"你好"}],'
        '"status":"processing"}],"tool_calls":[],"last_error":{}}',
    )
    assert normalize(raw) == [TextDelta("你好")]


def test_init_frame_with_empty_parts_is_ignored():
    raw = RawSSEEvent(
        None,
        '{"id":"msg-1","conversation_id":"conv-1","assistant_id":"a",'
        '"parts":[],"created_at":"2026-09-11","status":"init","last_error":{},'
        '"meta_data":{"input_question_type":"xxxx"}}',
    )
    assert normalize(raw) == []


def test_empty_parts_with_last_error_is_an_error():
    raw = RawSSEEvent(
        None,
        '{"status":"finish","parts":[],"last_error":{"message":"风控拦截"}}',
    )
    result = normalize(raw)
    assert len(result) == 1
    assert result[0].message == "风控拦截"


def test_truthy_tool_calls_without_parts_stays_a_tool_event():
    result = normalize(
        RawSSEEvent(None, '{"tool_calls":[{"name":"search","args":{}}]}')
    )
    assert len(result) == 1
    assert result[0].__class__.__name__ == "ToolEvent"


def test_part_level_finish_does_not_end_the_stream():
    # Live stream 2026-09-11: think part reaches status "finish" long before
    # the answer completes; it must not emit an OpenAI finish_reason chunk.
    raw = RawSSEEvent(
        None,
        '{"status":"processing",'
        '"parts":[{"answer_type":"think","text":"想完了","status":"finish"}]}',
    )
    assert normalize(raw) == [ReasoningDelta("想完了")]


def _texts(events):
    return [event.text for event in events if isinstance(event, TextDelta)]


def test_stream_normalizer_diffs_cumulative_snapshots():
    normalizer = StreamNormalizer()
    frames = [
        '{"parts":[{"answer_type":"text","text":"我是GLM"}]}',
        '{"parts":[{"answer_type":"text","text":"我是GLM，由智谱开发"}]}',
        '{"parts":[{"answer_type":"text","text":"我是GLM，由智谱开发"}]}',
        '{"status":"finish","parts":[{"answer_type":"text","text":"我是GLM，由智谱开发。","status":"finish"}]}',
    ]
    output = []
    for frame in frames:
        output.extend(normalizer.normalize(RawSSEEvent(None, frame)))
    assert _texts(output) == ["我是GLM", "，由智谱开发", "。"]
    assert isinstance(output[-1], Finish)


def test_stream_normalizer_passes_incremental_deltas_through():
    normalizer = StreamNormalizer()
    frames = [
        '{"parts":[{"answer_type":"text","text":"你"}]}',
        '{"parts":[{"answer_type":"text","text":"好"}]}',
    ]
    output = []
    for frame in frames:
        output.extend(normalizer.normalize(RawSSEEvent(None, frame)))
    assert _texts(output) == ["你", "好"]


def test_stream_normalizer_keeps_reasoning_channel_separate():
    normalizer = StreamNormalizer()
    frames = [
        '{"parts":[{"answer_type":"think","text":"第一步"},'
        '{"answer_type":"text","text":"答案"}]}',
        '{"parts":[{"answer_type":"think","text":"第一步，第二步"},'
        '{"answer_type":"text","text":"答案"}]}',
    ]
    reasoning = []
    text = []
    for frame in frames:
        for event in normalizer.normalize(RawSSEEvent(None, frame)):
            if isinstance(event, ReasoningDelta):
                reasoning.append(event.text)
            elif isinstance(event, TextDelta):
                text.append(event.text)
    assert reasoning == ["第一步", "，第二步"]
    assert text == ["答案"]
