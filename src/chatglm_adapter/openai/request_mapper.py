from ..config import Settings
from ..core.errors import UnsupportedFeatureError
from .schemas import ChatCompletionRequest


SUPPORTED_PARAMETERS = {
    "model",
    "messages",
    "stream",
    "temperature",
    "top_p",
    "max_tokens",
    "stop",
    "web_search",
    "reasoning_effort",
    "tools",
    "tool_choice",
}


def validate_request(request: ChatCompletionRequest, settings: Settings) -> list[str]:
    if request.tools is not None or request.tool_choice is not None:
        raise UnsupportedFeatureError(
            "Tool calling is not enabled for this ChatGLM Web adapter."
        )
    ignored = sorted(request.extra_parameter_names - SUPPORTED_PARAMETERS)
    if settings.strict_parameters and ignored:
        names = ", ".join(ignored)
        raise ValueError(f"unsupported parameters in strict mode: {names}")
    return ignored

