from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContentPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "text"
    text: str = ""


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[ContentPart]
    name: str | None = None

    @model_validator(mode="after")
    def require_text_content(self):
        if isinstance(self.content, list) and any(part.type != "text" for part in self.content):
            raise ValueError("only text message content is supported")
        return self


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[Message] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    web_search: bool = False
    reasoning_effort: Literal["low", "high", "max"] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None

    @property
    def extra_parameter_names(self) -> set[str]:
        return set(self.model_extra or {})


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "chatglm-web"
    reasoning_efforts: list[str] | None = None


class ModelsResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]
