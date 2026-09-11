import pytest

from chatglm_adapter.config import Settings
from chatglm_adapter.core.errors import UnsupportedFeatureError
from chatglm_adapter.openai.request_mapper import validate_request
from chatglm_adapter.openai.schemas import ChatCompletionRequest


def request(**extra):
    return ChatCompletionRequest(
        model="chatglm-glm-5.3-flash",
        messages=[{"role": "user", "content": "hello"}],
        **extra,
    )


def test_tools_are_rejected_explicitly():
    with pytest.raises(UnsupportedFeatureError):
        validate_request(request(tools=[{"type": "function"}]), Settings())


def test_unknown_parameters_are_reported_by_name_only():
    value = request(temperature=0.2, presence_penalty=0.7)
    assert validate_request(value, Settings()) == ["presence_penalty"]


def test_both_models_are_registered_with_reasoning_efforts():
    settings = Settings()
    assert settings.public_models == {
        "chatglm-glm-5.3-flash": "glm-5.3-flash",
        "chatglm-glm-5.3": "glm-5.3",
    }
    assert settings.reasoning_efforts_for("chatglm-glm-5.3") == ["low", "high", "max"]
