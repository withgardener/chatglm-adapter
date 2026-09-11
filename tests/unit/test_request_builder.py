import pytest

from chatglm_adapter.chatglm.request_builder import ChatGLMRequestBuilder
from chatglm_adapter.chatglm.upload import UploadedImage
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


def test_request_builder_maps_image_parts_to_uploaded_references():
    request = ChatCompletionRequest(
        model="chatglm-glm-5.3",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "图中是什么"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
                ],
            }
        ],
    )
    uploaded = UploadedImage(
        file_id="fid-1",
        image_url="https://t1.chatglm.cn/file/fid-1.jpg?sign=x",
        file_name="image.png",
        file_size=100,
    )
    body = ChatGLMRequestBuilder("glm-5.3").build(request, "conv", {(0, 1): uploaded}).body
    content = body["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "图中是什么"}
    assert content[1]["type"] == "image"
    assert content[1]["image"] == [
        {
            "file_name": "image.png",
            "file_id": "fid-1",
            "image_url": "https://t1.chatglm.cn/file/fid-1.jpg?sign=x",
            "file_size": 100,
            "order": 0,
            "width": 0,
            "height": 0,
        }
    ]


def test_request_builder_requires_uploaded_image_for_image_parts():
    request = ChatCompletionRequest(
        model="chatglm-glm-5.3",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AA=="},
                    }
                ],
            }
        ],
    )
    with pytest.raises(ValueError, match="not uploaded"):
        ChatGLMRequestBuilder("glm-5.3").build(request, "conv")
