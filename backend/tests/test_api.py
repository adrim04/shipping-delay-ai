"""Pruebas de integración de la API (pytest)."""
import io
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import BASE_DATASET  # noqa: E402
from app.main import app  # noqa: E402

API = "/api/v1"
SAMPLE = {"warehouse_block": "F", "mode_of_shipment": "Ship", "customer_care_calls": 4,
          "customer_rating": 3, "cost_of_the_product": 210, "prior_purchases": 3,
          "product_importance": "medium", "gender": "F", "discount_offered": 45,
          "weight_in_gms": 1500}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:      # ejecuta el lifespan (crea tablas + modelo inicial)
        yield c


def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["active_model"]


def test_predict_and_history(client):
    r = client.post(f"{API}/predictions", json=SAMPLE)
    assert r.status_code == 201
    body = r.json()
    assert body["predicted_class"] in (0, 1) and 0 <= body["probability_delay"] <= 1
    h = client.get(f"{API}/predictions?limit=5").json()
    assert h["total"] >= 1 and h["items"][0]["id"] == body["id"]
    assert client.get(f"{API}/predictions/{body['id']}").status_code == 200


def test_history_filter_by_model_version(client):
    version = client.post(f"{API}/predictions", json=SAMPLE).json()["model_version"]
    h = client.get(f"{API}/predictions", params={"model_version": version}).json()
    assert h["total"] >= 1 and all(p["model_version"] == version for p in h["items"])
    assert client.get(f"{API}/predictions", params={"model_version": "v-no-existe"}).status_code == 404


def test_predict_validation(client):
    bad = {**SAMPLE, "mode_of_shipment": "Train"}
    assert client.post(f"{API}/predictions", json=bad).status_code == 422


def test_metrics(client):
    m = client.get(f"{API}/metrics").json()
    assert m["status"] == "ACTIVO"
    assert m["roc_auc"] >= m["quality_thresholds"]["roc_auc"]


def test_upload_rejects_bad_csv(client):
    f = io.BytesIO(b"a,b\n1,2\n")
    r = client.post(f"{API}/datasets", files={"file": ("bad.csv", f, "text/csv")})
    assert r.status_code == 422


def test_upload_and_retrain(client):
    df = pd.read_csv(BASE_DATASET, encoding="utf-8-sig").sample(3000, random_state=1)
    buf = io.BytesIO(df.to_csv(index=False).encode())
    r = client.post(f"{API}/datasets", files={"file": ("nuevo.csv", buf, "text/csv")})
    assert r.status_code == 201
    ds_id = r.json()["id"]
    r = client.post(f"{API}/retrain", json={"dataset_id": ds_id, "algorithm": "LogisticRegression"})
    assert r.status_code == 200
    assert r.json()["status"] in ("COMPLETADO", "RECHAZADO")
    assert len(client.get(f"{API}/models").json()) >= 2
