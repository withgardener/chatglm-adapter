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
    assert body["conversation_id"] == "conv"
    assert body["meta_data"]["selected_model"] == "glm-5.3-flash"
    assert body["meta_data"]["is_networking"] is True
    assert body["messages"][0]["content"] == [{"type": "text", "text": "be concise"}]

