"""Lógica de negocio: registro de modelos, predicción, reentrenamiento."""
import json
import shutil
import threading
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app import models
from app.config import ARTIFACTS_DIR, BASE_DATASET, QUALITY_THRESHOLDS, UPLOAD_DIR, utcnow
from app.ml import pipeline as ml

_lock = threading.Lock()
_cache: dict = {"version": None, "pipeline": None}


# ------------------------------------------------------------ serialización
def model_to_dict(m: models.ModelVersion) -> dict:
    return {
        "id": m.id, "version": m.version, "algorithm": m.algorithm, "status": m.status,
        "hyperparameters": json.loads(m.hyperparameters or "{}"),
        "dataset_id": m.dataset_id, "train_rows": m.train_rows, "test_rows": m.test_rows,
        "accuracy": m.accuracy, "precision": m.precision, "recall": m.recall,
        "f1_score": m.f1_score, "roc_auc": m.roc_auc, "cv_roc_auc": m.cv_roc_auc,
        "confusion_matrix": json.loads(m.confusion_matrix or "{}"),
        "feature_importance": json.loads(m.feature_importance or "[]"),
        "comparison": json.loads(m.comparison or "[]"),
        "quality_thresholds": QUALITY_THRESHOLDS,
        "quality_notes": m.quality_notes, "trained_at": m.trained_at,
    }


def dataset_to_dict(d: models.Dataset) -> dict:
    return {"id": d.id, "filename": d.filename, "row_count": d.row_count,
            "class_balance": json.loads(d.class_balance or "{}"),
            "validation_notes": json.loads(d.validation_notes or "[]"),
            "uploaded_at": d.uploaded_at}


# ------------------------------------------------------------ datasets
def register_dataset(db: Session, src: Path, filename: str, copy: bool = True) -> models.Dataset:
    df = ml.load_dataset(src)
    report = ml.validate_dataset(df)          # lanza DatasetValidationError
    if copy:
        dest = UPLOAD_DIR / f"{utcnow():%Y%m%d%H%M%S%f}_{Path(filename).name}"
        shutil.copy(src, dest)
    else:
        dest = src
    ds = models.Dataset(filename=filename, storage_path=str(dest), row_count=report["rows"],
                        class_balance=json.dumps(report["class_balance"]),
                        validation_notes=json.dumps(report["issues"], ensure_ascii=False))
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


# ------------------------------------------------------------ modelos
def get_active_model(db: Session) -> models.ModelVersion | None:
    return (db.query(models.ModelVersion).filter_by(status="ACTIVO")
            .order_by(models.ModelVersion.id.desc()).first())


def _get_pipeline(mv: models.ModelVersion):
    if _cache["version"] != mv.version:
        _cache["pipeline"] = ml.load_model(mv.artifact_path)
        _cache["version"] = mv.version
    return _cache["pipeline"]


def train_new_version(db: Session, dataset: models.Dataset, algorithm: str = "auto"):
    """Entrena, evalúa y aplica la compuerta de calidad. Devuelve (modelo, aprobado, mensaje)."""
    with _lock:
        df = ml.load_dataset(dataset.storage_path)
        result = ml.train_and_select(df, only=algorithm)
        ok, failures = ml.passes_quality_gate(result.metrics)
        version = f"v{utcnow():%Y%m%d-%H%M%S-%f}"[:-3]
        path = ml.save_model(result, ARTIFACTS_DIR, version)

        mv = models.ModelVersion(
            version=version, algorithm=result.algorithm,
            hyperparameters=json.dumps(result.params), dataset_id=dataset.id,
            train_rows=result.train_rows, test_rows=result.test_rows,
            accuracy=result.metrics["accuracy"], precision=result.metrics["precision"],
            recall=result.metrics["recall"], f1_score=result.metrics["f1"],
            roc_auc=result.metrics["roc_auc"], cv_roc_auc=result.metrics["cv_roc_auc"],
            confusion_matrix=json.dumps(result.metrics["confusion_matrix"]),
            feature_importance=json.dumps(ml.feature_importance(result.pipeline)),
            comparison=json.dumps(result.comparison), artifact_path=str(path),
            status="ACTIVO" if ok else "RECHAZADO",
            quality_notes="Supera todos los umbrales de calidad" if ok
            else "No supera: " + "; ".join(failures))
        if ok:
            db.query(models.ModelVersion).filter_by(status="ACTIVO").update({"status": "INACTIVO"})
        db.add(mv)
        db.commit()
        db.refresh(mv)
        msg = (f"Modelo {version} ({result.algorithm}) activado." if ok else
               f"Modelo {version} rechazado por la compuerta de calidad: {', '.join(failures)}. "
               "Se mantiene el modelo anterior.")
        return mv, ok, msg


def bootstrap(db: Session) -> None:
    """Al iniciar: si no hay modelo activo, registra el dataset base y entrena."""
    if get_active_model(db):
        return
    ds = db.query(models.Dataset).order_by(models.Dataset.id).first()
    if ds is None:
        ds = register_dataset(db, BASE_DATASET, BASE_DATASET.name, copy=False)
    train_new_version(db, ds)


# ------------------------------------------------------------ predicción
def predict(db: Session, data: dict) -> tuple[models.Prediction, models.ModelVersion]:
    mv = get_active_model(db)
    if mv is None:
        raise RuntimeError("No hay un modelo activo.")
    row = pd.DataFrame([{
        "Warehouse_block": data["warehouse_block"], "Mode_of_Shipment": data["mode_of_shipment"],
        "Customer_care_calls": data["customer_care_calls"], "Customer_rating": data["customer_rating"],
        "Cost_of_the_Product": data["cost_of_the_product"], "Prior_purchases": data["prior_purchases"],
        "Product_importance": data["product_importance"], "Gender": data["gender"],
        "Discount_offered": data["discount_offered"], "Weight_in_gms": data["weight_in_gms"],
    }])[ml.FEATURES]
    pipe = _get_pipeline(mv)
    proba = float(pipe.predict_proba(row)[0, 1])
    cls = int(proba >= 0.5)
    pred = models.Prediction(model_version_id=mv.id, **data, predicted_class=cls,
                             predicted_label=ml.LABELS[cls], probability_delay=round(proba, 4))
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred, mv
