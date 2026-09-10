import json

from chatglm_adapter.core.events import Finish, ReasoningDelta, TextDelta
from chatglm_adapter.openai.response_encoder import CompletionAccumulator, OpenAIEncoder


def test_stream_encoder_emits_openai_deltas():
    encoder = OpenAIEncoder("chatglm-glm-5.3-flash")
    accumulator = CompletionAccumulator()
    json.loads(encoder.role_chunk().split("data: ", 1)[1])
    reasoning = encoder.event(ReasoningDelta("think"), accumulator)
    content = encoder.event(TextDelta("answer"), accumulator)
    finish = encoder.event(Finish("stop"), accumulator)
    assert '"reasoning_content":"think"' in reasoning
    assert '"content":"answer"' in content
    assert '"finish_reason":"stop"' in finish
    assert accumulator.message()["reasoning_content"] == "think"

