"""Configuración central del servicio de IA."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

for d in (DATA_DIR, UPLOAD_DIR, ARTIFACTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# SQLite por defecto; para PostgreSQL:
#   DATABASE_URL=postgresql+psycopg2://usuario:clave@localhost:5432/shipping_ai
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'shipping_ai.db'}")

BASE_DATASET = DATA_DIR / "Train.csv"

# Umbrales de calidad (CRISP-ML(Q)): un modelo solo se activa si los cumple.
QUALITY_THRESHOLDS = {
    "roc_auc": float(os.getenv("MIN_ROC_AUC", 0.70)),
    "accuracy": float(os.getenv("MIN_ACCURACY", 0.65)),
    "f1": float(os.getenv("MIN_F1", 0.60)),
}

MIN_TRAINING_ROWS = 500
RANDOM_STATE = 42


def utcnow():
    """Fecha/hora UTC (naive) para columnas TIMESTAMP."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)
