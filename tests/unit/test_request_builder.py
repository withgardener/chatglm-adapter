import pytest

from chatglm_adapter.chatglm.request_builder import ChatGLMRequestBuilder
from chatglm_adapter.openai.schemas import ChatCompletionRequest


def test_request_builder_maps_messages_and_search():
    request = ChatCompletionRequest(
        model="chatglm-glm-5.3-flash",
        messages=[
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "hello"},
        ],
        web_search=True,
    )
    body = ChatGLMRequestBuilder("glm-5.3-flash").build(request, "conv").body
    assert body["assistant_id"] == "65940acff94777010aa6b796"
    assert body["conversation_id"] == "conv"
    assert body["meta_data"]["selected_model"] == "glm-5.3-flash"
    assert body["meta_data"]["is_networking"] is True
    assert body["messages"][0]["content"] == [{"type": "text", "text": "be concise"}]


@pytest.mark.parametrize(
    ("effort", "chat_mode"),
    [(None, "deep_thinking"), ("low", ""), ("high", "thinking"), ("max", "deep_thinking")],
)
def test_request_builder_maps_reasoning_effort_to_web_chat_mode(effort, chat_mode):
    request = ChatCompletionRequest(
        model="chatglm-glm-5.3",
        messages=[{"role": "user", "content": "hello"}],
        reasoning_effort=effort,
    )
    body = ChatGLMRequestBuilder("glm-5.3").build(request, "").body
    assert body["meta_data"]["selected_model"] == "glm-5.3"
    assert body["meta_data"]["chat_mode"] == chat_mode
