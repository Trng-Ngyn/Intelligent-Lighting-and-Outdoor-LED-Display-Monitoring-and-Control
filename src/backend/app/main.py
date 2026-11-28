from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, assets, controls, analytics
import core_api

app = FastAPI(
    title="Intelligent Lighting Core API",
    version="1.0.0",
    description="FastAPI Core API - W5 Backend",
    openapi_url="/openapi.json",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

@app.on_event("startup")
def startup_mqtt():
    core_api.configure_logging()
    core_api.init_mqtt()

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "core-api"}

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(assets.router, prefix="/api/v1/assets", tags=["Assets"])
app.include_router(controls.router, prefix="/api/v1/controls/lighting", tags=["Lighting Controls"])
app.include_router(analytics.router, prefix="/api/v1/analytics/telemetry", tags=["Analytics"])
