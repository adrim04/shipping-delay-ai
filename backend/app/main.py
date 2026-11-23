"""
Servicio de IA – Predicción de retrasos en envíos de e-commerce.
Ejecutar:  uvicorn app.main:app --reload   (desde la carpeta backend/)
Swagger UI: http://localhost:8000/docs   |   OpenAPI: http://localhost:8000/openapi.json
"""
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import models, schemas, services
from app.config import FRONTEND_DIR, utcnow
from app.database import Base, SessionLocal, engine, get_db
from app.ml.pipeline import DatasetValidationError

API = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        services.bootstrap(db)
    finally:
        db.close()
    yield


tags = [
    {"name": "Predicción", "description": "Enviar datos de un envío y obtener la predicción."},
    {"name": "Historial", "description": "Consultar predicciones realizadas anteriormente."},
    {"name": "Métricas", "description": "Rendimiento del modelo activo y versiones anteriores."},
    {"name": "Datasets", "description": "Subir y listar archivos de entrenamiento."},
    {"name": "Reentrenamiento", "description": "Reentrenar el modelo con datos actualizados."},
    {"name": "Sistema", "description": "Estado del servicio."},
]

app = FastAPI(
    title="Shipping Delay AI – API",
    version="1.0.0",
    description=(
        "API REST que expone un modelo de **clasificación supervisada** entrenado con el dataset "
        "*E-Commerce Shipping Data* (Kaggle, prachi13/customer-analytics). Predice si un envío "
        "llegará **a tiempo (0)** o **con retraso (1)**.\n\n"
        "El ciclo de vida del modelo sigue **CRISP-ML(Q)**: cada reentrenamiento pasa por una "
        "compuerta de calidad antes de activarse."),
    openapi_tags=tags,
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ sistema
@app.get(f"{API}/health", response_model=schemas.HealthResponse, tags=["Sistema"],
         summary="Estado del servicio")
def health(db: Session = Depends(get_db)):
    mv = services.get_active_model(db)
    return {"status": "ok", "active_model": mv.version if mv else None}


# ------------------------------------------------------------------ predicción
@app.post(f"{API}/predictions", response_model=schemas.PredictionResult, status_code=201,
          tags=["Predicción"], summary="Predecir si un envío llegará con retraso")
def create_prediction(payload: schemas.ShipmentInput, db: Session = Depends(get_db)):
    try:
        pred, mv = services.predict(db, payload.model_dump())
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {"id": pred.id, "predicted_class": pred.predicted_class,
            "predicted_label": pred.predicted_label, "probability_delay": pred.probability_delay,
            "model_version": mv.version, "created_at": pred.created_at}


# ------------------------------------------------------------------ historial
@app.get(f"{API}/predictions", response_model=schemas.PredictionHistory, tags=["Historial"],
         summary="Historial de predicciones (datos enviados y resultado)")
def list_predictions(limit: int = Query(20, ge=1, le=500), offset: int = Query(0, ge=0),
                     predicted_class: int | None = Query(None, ge=0, le=1,
                                                         description="Filtrar por clase"),
                     db: Session = Depends(get_db)):
    q = db.query(models.Prediction)
    if predicted_class is not None:
        q = q.filter(models.Prediction.predicted_class == predicted_class)
    total = q.count()
    rows = q.order_by(models.Prediction.id.desc()).offset(offset).limit(limit).all()
    items = []
    for p in rows:
        d = schemas.PredictionRecord.model_validate(
            {**{c.name: getattr(p, c.name) for c in p.__table__.columns},
             "model_version": p.model_version.version})
        items.append(d)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get(f"{API}/predictions/{{prediction_id}}", response_model=schemas.PredictionRecord,
         tags=["Historial"], summary="Detalle de una predicción")
def get_prediction(prediction_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Prediction, prediction_id)
    if not p:
        raise HTTPException(404, "Predicción no encontrada")
    return {**{c.name: getattr(p, c.name) for c in p.__table__.columns},
            "model_version": p.model_version.version}


# ------------------------------------------------------------------ métricas
@app.get(f"{API}/metrics", response_model=schemas.ModelMetrics, tags=["Métricas"],
         summary="Métricas de rendimiento del modelo activo")
def get_metrics(db: Session = Depends(get_db)):
    mv = services.get_active_model(db)
    if not mv:
        raise HTTPException(404, "No hay un modelo activo")
    return services.model_to_dict(mv)


@app.get(f"{API}/models", response_model=list[schemas.ModelMetrics], tags=["Métricas"],
         summary="Todas las versiones del modelo (activas, inactivas y rechazadas)")
def list_models(db: Session = Depends(get_db)):
    rows = db.query(models.ModelVersion).order_by(models.ModelVersion.id.desc()).all()
    return [services.model_to_dict(m) for m in rows]


# ------------------------------------------------------------------ datasets
@app.post(f"{API}/datasets", response_model=schemas.DatasetInfo, status_code=201,
          tags=["Datasets"], summary="Subir un archivo CSV de entrenamiento")
async def upload_dataset(file: UploadFile = File(..., description="CSV con las 12 columnas del dataset"),
                         db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "El archivo debe ser .csv")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        ds = services.register_dataset(db, tmp_path, file.filename)
    except DatasetValidationError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # CSV ilegible
        raise HTTPException(400, f"No se pudo leer el CSV: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)
    return services.dataset_to_dict(ds)


@app.get(f"{API}/datasets", response_model=list[schemas.DatasetInfo], tags=["Datasets"],
         summary="Listar datasets disponibles")
def list_datasets(db: Session = Depends(get_db)):
    rows = db.query(models.Dataset).order_by(models.Dataset.id.desc()).all()
    return [services.dataset_to_dict(d) for d in rows]


# ------------------------------------------------------------------ reentrenamiento
@app.post(f"{API}/retrain", response_model=schemas.RetrainResponse, tags=["Reentrenamiento"],
          summary="Reentrenar el modelo con un dataset (por defecto, el último subido)")
def retrain(body: schemas.RetrainRequestIn | None = None, db: Session = Depends(get_db)):
    body = body or schemas.RetrainRequestIn()
    if body.dataset_id:
        ds = db.get(models.Dataset, body.dataset_id)
        if not ds:
            raise HTTPException(404, "Dataset no encontrado")
    else:
        ds = db.query(models.Dataset).order_by(models.Dataset.id.desc()).first()
    previous = services.get_active_model(db)
    prev_version = previous.version if previous else None

    req = models.RetrainRequest(dataset_id=ds.id, algorithm=body.algorithm, status="EN_PROCESO")
    db.add(req)
    db.commit()
    try:
        mv, ok, msg = services.train_new_version(db, ds, body.algorithm)
        req.status, req.resulting_model_id, req.message = (
            "COMPLETADO" if ok else "RECHAZADO"), mv.id, msg
    except Exception as e:
        req.status, req.message = "ERROR", str(e)
        req.finished_at = utcnow()
        db.commit()
        raise HTTPException(500, f"Error al reentrenar: {e}")
    req.finished_at = utcnow()
    db.commit()
    return {"request_id": req.id, "status": req.status, "message": msg,
            "new_model": services.model_to_dict(mv), "previous_model_version": prev_version}


# ------------------------------------------------------------------ cliente web
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/app/")
