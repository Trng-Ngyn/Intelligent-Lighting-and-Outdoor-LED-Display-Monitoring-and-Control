
from fastapi import FastAPI, HTTPException
from .schemas import PredictRequest, PredictResponse
from .model_loader import ModelBundle
from .predictor import predict_batch

app = FastAPI(
    title="W5-ML AI Inference Service",
    description="Microservice du doan bat thuong den LED F01-F04",
    version="1.0.0"
)

models = ModelBundle()


@app.on_event("startup")
def startup():
    models.load()


@app.get("/")
def root():
    return {
        "service": "W5-ML AI Inference",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    all_loaded = all(
        models.status.get(key) == "loaded"
        for key in [
            "isolation_forest",
            "preprocessor",
            "autoencoder",
            "threshold"
        ]
    )

    return {
        "status": "ok" if all_loaded else "degraded",
        "models": models.status
    }


@app.post(
    "/api/v1/ai/predict-anomaly",
    response_model=PredictResponse
)
def predict(request: PredictRequest):
    try:
        results = predict_batch(request.batch, models)

        return {
            "success": True,
            "total_samples": len(results),
            "results": results,
            "model_status": models.status
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Inference error: {exc}"
        )
