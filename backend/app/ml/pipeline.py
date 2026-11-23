"""
Pipeline de Machine Learning siguiendo CRISP-ML(Q).

Fases cubiertas en este módulo:
  2. Ingeniería de datos   -> load_dataset(), validate_dataset()
  3. Ingeniería del modelo -> build_candidates(), train_and_select()
  4. Evaluación del modelo -> evaluate(), passes_quality_gate()
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.config import MIN_TRAINING_ROWS, QUALITY_THRESHOLDS, RANDOM_STATE, utcnow

TARGET = "Reached.on.Time_Y.N"
CATEGORICAL = ["Warehouse_block", "Mode_of_Shipment", "Product_importance", "Gender"]
NUMERIC = ["Customer_care_calls", "Customer_rating", "Cost_of_the_Product",
           "Prior_purchases", "Discount_offered", "Weight_in_gms"]
FEATURES = CATEGORICAL + NUMERIC

ALLOWED_VALUES = {
    "Warehouse_block": {"A", "B", "C", "D", "F"},
    "Mode_of_Shipment": {"Flight", "Ship", "Road"},
    "Product_importance": {"low", "medium", "high"},
    "Gender": {"F", "M"},
}
NUMERIC_RANGES = {   # rangos razonables (dominio), más amplios que los observados
    "Customer_care_calls": (0, 20),
    "Customer_rating": (1, 5),
    "Cost_of_the_Product": (1, 2000),
    "Prior_purchases": (0, 50),
    "Discount_offered": (0, 100),
    "Weight_in_gms": (1, 20000),
}

# En el dataset original: 1 = el envío NO llegó a tiempo, 0 = llegó a tiempo.
LABELS = {0: "A tiempo", 1: "Con retraso"}


class DatasetValidationError(ValueError):
    pass


# ---------------------------------------------------------------- datos
def load_dataset(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python")
    df.columns = [c.strip() for c in df.columns]
    return df


def validate_dataset(df: pd.DataFrame) -> dict:
    """Aseguramiento de calidad de datos. Lanza DatasetValidationError si falla."""
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise DatasetValidationError(f"Faltan columnas obligatorias: {missing}")
    if len(df) < MIN_TRAINING_ROWS:
        raise DatasetValidationError(
            f"El dataset tiene {len(df)} filas; se requieren al menos {MIN_TRAINING_ROWS}.")

    issues = []
    nulls = int(df[FEATURES + [TARGET]].isna().sum().sum())
    if nulls:
        issues.append(f"{nulls} valores nulos (se eliminarán las filas)")
    if not set(df[TARGET].dropna().unique()).issubset({0, 1}):
        raise DatasetValidationError(f"La columna {TARGET} solo puede contener 0 y 1.")
    for col, allowed in ALLOWED_VALUES.items():
        bad = set(df[col].dropna().astype(str).unique()) - allowed
        if bad:
            raise DatasetValidationError(f"Valores no permitidos en {col}: {sorted(bad)}")
    for col in NUMERIC:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise DatasetValidationError(f"La columna {col} debe ser numérica.")
        lo, hi = NUMERIC_RANGES[col]
        out = int(((df[col] < lo) | (df[col] > hi)).sum())
        if out:
            issues.append(f"{out} valores fuera de rango en {col} (se eliminarán)")
    dups = int(df.duplicated().sum())
    if dups:
        issues.append(f"{dups} filas duplicadas (se eliminarán)")

    balance = df[TARGET].value_counts(normalize=True).round(3).to_dict()
    return {"rows": int(len(df)), "issues": issues,
            "class_balance": {str(k): v for k, v in balance.items()}}


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df[FEATURES + [TARGET]].dropna().drop_duplicates().copy()
    for col, (lo, hi) in NUMERIC_RANGES.items():
        df = df[(df[col] >= lo) & (df[col] <= hi)]
    df[TARGET] = df[TARGET].astype(int)
    return df


# ---------------------------------------------------------------- modelo
def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC),
    ])


def build_candidates() -> dict:
    """Modelos candidatos con su espacio de hiperparámetros."""
    return {
        "LogisticRegression": (
            LogisticRegression(max_iter=2000),
            {"clf__C": [0.1, 1.0, 10.0]},
        ),
        "RandomForest": (
            RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1),
            {"clf__n_estimators": [200], "clf__max_depth": [6, 8, 10],
             "clf__min_samples_leaf": [5, 10]},
        ),
        "GradientBoosting": (
            GradientBoostingClassifier(random_state=RANDOM_STATE),
            {"clf__n_estimators": [100, 150], "clf__max_depth": [2, 3],
             "clf__learning_rate": [0.05, 0.1]},
        ),
    }


@dataclass
class TrainingResult:
    pipeline: Pipeline
    algorithm: str
    params: dict
    metrics: dict
    comparison: list = field(default_factory=list)
    train_rows: int = 0
    test_rows: int = 0


def evaluate(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series) -> dict:
    pred = pipeline.predict(X)
    proba = pipeline.predict_proba(X)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y, proba)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def feature_importance(pipeline: Pipeline) -> list[dict]:
    pre = pipeline.named_steps["pre"]
    clf = pipeline.named_steps["clf"]
    names = pre.get_feature_names_out()
    if hasattr(clf, "feature_importances_"):
        values = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        values = np.abs(clf.coef_[0])
    else:
        return []
    names = [n.replace("cat__", "").replace("num__", "") for n in names]
    ranked = sorted(zip(names, values), key=lambda t: t[1], reverse=True)
    return [{"feature": n, "importance": round(float(v), 4)} for n, v in ranked]


def train_and_select(df: pd.DataFrame, only: str | None = None) -> TrainingResult:
    """Entrena candidatos con validación cruzada y elige el de mejor ROC-AUC."""
    df = clean_dataset(df)
    X, y = df[FEATURES], df[TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    candidates = build_candidates()
    if only and only != "auto":
        if only not in candidates:
            raise ValueError(f"Algoritmo desconocido: {only}")
        candidates = {only: candidates[only]}

    best, comparison = None, []
    for name, (estimator, grid) in candidates.items():
        pipe = Pipeline([("pre", _preprocessor()), ("clf", estimator)])
        search = GridSearchCV(pipe, grid, scoring="roc_auc", cv=cv, n_jobs=-1)
        search.fit(X_tr, y_tr)
        test_metrics = evaluate(search.best_estimator_, X_te, y_te)
        row = {"algorithm": name, "cv_roc_auc": round(float(search.best_score_), 4),
               "params": {k.replace("clf__", ""): v for k, v in search.best_params_.items()},
               **{k: v for k, v in test_metrics.items() if k != "confusion_matrix"}}
        comparison.append(row)
        if best is None or search.best_score_ > best[1].best_score_:
            best = (name, search, test_metrics)

    name, search, test_metrics = best
    test_metrics["cv_roc_auc"] = round(float(search.best_score_), 4)
    return TrainingResult(
        pipeline=search.best_estimator_, algorithm=name,
        params={k.replace("clf__", ""): v for k, v in search.best_params_.items()},
        metrics=test_metrics, comparison=comparison,
        train_rows=len(X_tr), test_rows=len(X_te))


def passes_quality_gate(metrics: dict) -> tuple[bool, list[str]]:
    failures = [f"{k}={metrics[k]} < {v}" for k, v in QUALITY_THRESHOLDS.items()
                if metrics.get(k, 0) < v]
    return (not failures, failures)


def save_model(result: TrainingResult, directory: Path, version: str) -> Path:
    path = directory / f"model_{version}.joblib"
    joblib.dump(result.pipeline, path)
    meta = {"version": version, "algorithm": result.algorithm, "params": result.params,
            "metrics": result.metrics, "comparison": result.comparison,
            "saved_at": utcnow().isoformat()}
    (directory / f"model_{version}.json").write_text(json.dumps(meta, indent=2))
    return path


def load_model(path: str | Path) -> Pipeline:
    return joblib.load(path)
