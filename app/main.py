import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routes.agent import router as agent_router
from app.routes.admin import router as admin_router
from app.config import get_settings
from app.metrics import record_request, resolve_route_label, router as metrics_router
from app.routes.health import router as health_router
from app.routes.ingest import router as ingest_router
from app.routes.media import router as media_router
from app.routes.query import router as query_router
from app.routes.session import router as session_router

_LOGGER = logging.getLogger("citeshield")
logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def instrument_requests(request: Request, call_next):
        start = perf_counter()
        status_code = 500
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_seconds = perf_counter() - start
            route = resolve_route_label(request)
            record_request(route=route, method=request.method, status_code=status_code, duration_seconds=duration_seconds)

            query_profile = getattr(request.state, "query_profile", {})
            payload = {
                "request_id": request_id,
                "route": route,
                "method": request.method,
                "status_code": status_code,
                "duration_ms": round(duration_seconds * 1000, 2),
                "tenant_id": getattr(request.state, "tenant_id", None),
                "retrieval_ms": query_profile.get("retrieval_ms"),
                "generation_ms": query_profile.get("generation_ms"),
                "citation_count": query_profile.get("citation_count"),
                "abstained": query_profile.get("abstained"),
            }
            _LOGGER.info(json.dumps(payload, sort_keys=True))

    app.include_router(health_router)
    app.include_router(session_router)
    app.include_router(admin_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(media_router)
    app.include_router(agent_router)
    app.include_router(metrics_router)
    return app


app = create_app()
