import time

from fastapi import APIRouter, Depends, Request

from .auth import require_internal_api_key
from ..openai.schemas import ModelCard, ModelsResponse

router = APIRouter()


@router.get(
    "/v1/models",
    response_model=ModelsResponse,
    dependencies=[Depends(require_internal_api_key)],
)
async def models(request: Request) -> ModelsResponse:
    settings = request.app.state.container.settings
    return ModelsResponse(
        data=[
            ModelCard(id=model_id, created=int(time.time()))
            for model_id in settings.public_models
        ]
    )
