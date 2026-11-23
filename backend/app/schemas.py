from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ShipmentInput(BaseModel):
    """Datos de un envío para predecir si llegará con retraso."""
    warehouse_block: Literal["A", "B", "C", "D", "F"] = Field(..., description="Bloque del almacén")
    mode_of_shipment: Literal["Flight", "Ship", "Road"] = Field(..., description="Modo de envío")
    customer_care_calls: int = Field(..., ge=0, le=20, description="Llamadas a atención al cliente")
    customer_rating: int = Field(..., ge=1, le=5, description="Calificación del cliente (1-5)")
    cost_of_the_product: float = Field(..., gt=0, le=2000, description="Costo del producto (USD)")
    prior_purchases: int = Field(..., ge=0, le=50, description="Compras previas del cliente")
    product_importance: Literal["low", "medium", "high"] = Field(..., description="Importancia del producto")
    gender: Literal["F", "M"] = Field(..., description="Género del cliente")
    discount_offered: float = Field(..., ge=0, le=100, description="Descuento ofrecido (%)")
    weight_in_gms: float = Field(..., gt=0, le=20000, description="Peso en gramos")

    model_config = ConfigDict(json_schema_extra={"example": {
        "warehouse_block": "F", "mode_of_shipment": "Ship", "customer_care_calls": 4,
        "customer_rating": 3, "cost_of_the_product": 210, "prior_purchases": 3,
        "product_importance": "medium", "gender": "F", "discount_offered": 45,
        "weight_in_gms": 1500}})


class PredictionResult(BaseModel):
    id: int
    predicted_class: int = Field(..., description="0 = a tiempo, 1 = con retraso")
    predicted_label: str
    probability_delay: float = Field(..., description="Probabilidad de retraso (0-1)")
    model_version: str
    created_at: datetime


class PredictionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    warehouse_block: str
    mode_of_shipment: str
    customer_care_calls: int
    customer_rating: int
    cost_of_the_product: float
    prior_purchases: int
    product_importance: str
    gender: str
    discount_offered: float
    weight_in_gms: float
    predicted_class: int
    predicted_label: str
    probability_delay: float
    model_version: str
    created_at: datetime


class PredictionHistory(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PredictionRecord]


class ModelMetrics(BaseModel):
    id: int
    version: str
    algorithm: str
    status: str
    hyperparameters: dict
    dataset_id: int
    train_rows: Optional[int]
    test_rows: Optional[int]
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    cv_roc_auc: Optional[float]
    confusion_matrix: dict
    feature_importance: list
    comparison: list
    quality_thresholds: dict
    quality_notes: Optional[str]
    trained_at: datetime


class DatasetInfo(BaseModel):
    id: int
    filename: str
    row_count: int
    class_balance: dict
    validation_notes: list
    uploaded_at: datetime


class RetrainRequestIn(BaseModel):
    dataset_id: Optional[int] = Field(None, description="Dataset a usar. Si se omite, se usa el último subido.")
    algorithm: Literal["auto", "LogisticRegression", "RandomForest", "GradientBoosting"] = "auto"


class RetrainResponse(BaseModel):
    request_id: int
    status: str = Field(..., description="COMPLETADO (modelo activado) o RECHAZADO (no superó el umbral de calidad)")
    message: str
    new_model: Optional[ModelMetrics]
    previous_model_version: Optional[str]


class HealthResponse(BaseModel):
    status: str
    active_model: Optional[str]
