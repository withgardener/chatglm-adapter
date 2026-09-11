import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..chatglm.request_builder import ChatGLMRequestBuilder
from ..chatglm.sse_parser import StreamNormalizer
from ..core.errors import AdapterError, QueueTimeoutError, UnsupportedFeatureError
from ..core.events import Error as UpstreamEventError
from ..core.events import Unknown
from ..openai.request_mapper import validate_request
from ..openai.response_encoder import CompletionAccumulator, OpenAIEncoder
from ..openai.schemas import ChatCompletionRequest
from .auth import require_internal_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_internal_api_key)],
)
async def chat_completions(request: Request, body: ChatCompletionRequest):
    container = request.app.state.container
    try:
        ignored = validate_request(body, container.settings)
    except UnsupportedFeatureError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": {"type": "unsupported_feature", "message": str(exc)}},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if ignored:
        logger.info("ignored request parameters", extra={"parameter_names": ignored})

    upstream_model = container.settings.public_models.get(body.model)
    if not upstream_model:
        return JSONResponse(
            status_code=400,
            content={"error": {"type": "invalid_request_error", "message": "unknown model"}},
        )
    builder = ChatGLMRequestBuilder(upstream_model, container.settings.chatglm_assistant_id)
    request_id = request.headers.get("X-Request-Id") or str(uuid4())
    lease = await _acquire(container)

    if body.stream:
        return StreamingResponse(
            _stream_body(container, body, builder, request_id, lease),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Request-Id": request_id},
        )
    try:
        async with lease:
            encoder = OpenAIEncoder(body.model)
            accumulator = CompletionAccumulator()
            normalizer = StreamNormalizer()
            async for raw in container.chatglm.stream(body, builder, request_id=request_id):
                for event in normalizer.normalize(raw):
                    if isinstance(event, UpstreamEventError):
                        return JSONResponse(
                            status_code=502,
                            content={"error": {"type": event.code, "message": event.message}},
                        )
                    encoder.event(event, accumulator)
            return encoder.non_stream(accumulator)
    except AdapterError as exc:
        return _error_response(exc)


async def _stream_body(container, body, builder, request_id, lease) -> AsyncIterator[str]:
    encoder = OpenAIEncoder(body.model)
    accumulator = CompletionAccumulator()
    normalizer = StreamNormalizer()
    try:
        yield encoder.role_chunk()
        async with lease:
            async for raw in container.chatglm.stream(body, builder, request_id=request_id):
                for event in normalizer.normalize(raw):
                    if isinstance(event, Unknown):
                        # Shapes contain only field names and type markers, no
                        # payload values, so this stays within the log policy.
                        logger.warning(
                            "unknown upstream SSE event: event=%s shape=%s",
                            event.event,
                            event.payload_shape,
                        )
                    chunk = encoder.event(event, accumulator)
                    if chunk:
                        yield chunk
        yield encoder.done()
    except asyncio.CancelledError:
        raise
    except AdapterError as exc:
        yield encoder._sse({"error": {"type": "upstream_error", "message": str(exc)}})
        yield encoder.done()


async def _acquire(container):
    try:
        return await container.gate.acquire()
    except QueueTimeoutError as exc:
        raise HTTPException(status_code=503, detail="upstream queue wait timed out") from exc


def _error_response(exc: AdapterError):
    if isinstance(exc, QueueTimeoutError):
        status = 503
    else:
        status = getattr(exc, "status_code", None) or 502
    return JSONResponse(
        status_code=status,
        content={"error": {"type": exc.__class__.__name__, "message": str(exc)}},
    )
