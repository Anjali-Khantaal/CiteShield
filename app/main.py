from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routes.admin import router as admin_router
from app.config import get_settings
from app.metrics import record_request, resolve_route_label, router as metrics_router
from app.routes.health import router as health_router
from app.routes.ingest import router as ingest_router
from app.routes.query import router as query_router
from app.routes.session import router as session_router


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
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            record_request(
                route=resolve_route_label(request),
                method=request.method,
                status_code=status_code,
                duration_seconds=perf_counter() - start,
            )

    app.include_router(health_router)
    app.include_router(session_router)
    app.include_router(admin_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(metrics_router)
    return app


app = create_app()
