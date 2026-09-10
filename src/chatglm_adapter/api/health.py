from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    container = request.app.state.container
    return {
        "status": "ok",
        "version": container.settings.version,
        "upstream": "chatglm.cn",
        "auth": "ready" if container.auth.ready else "not_configured",
        "queue_depth": container.gate.depth,
    }


@router.get("/ready")
async def ready(request: Request):
    container = request.app.state.container
    if not container.auth.ready:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "auth configuration is incomplete"},
        )
    return {"status": "ready"}

