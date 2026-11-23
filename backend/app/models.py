"""Modelo de datos (ORM). Ver backend/db/schema.sql y docs/diagrama_bd.png."""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.config import utcnow
from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    row_count = Column(Integer, nullable=False)
    class_balance = Column(Text)            # JSON {"0": 0.40, "1": 0.60}
    validation_notes = Column(Text)         # JSON lista de observaciones
    uploaded_at = Column(DateTime, default=utcnow, nullable=False)

    model_versions = relationship("ModelVersion", back_populates="dataset")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(50), unique=True, nullable=False)
    algorithm = Column(String(100), nullable=False)
    hyperparameters = Column(Text)          # JSON
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    train_rows = Column(Integer)
    test_rows = Column(Integer)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    roc_auc = Column(Float)
    cv_roc_auc = Column(Float)
    confusion_matrix = Column(Text)         # JSON {"tn":..,"fp":..,"fn":..,"tp":..}
    feature_importance = Column(Text)       # JSON
    comparison = Column(Text)               # JSON: resultado de todos los candidatos
    artifact_path = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False)   # ACTIVO | INACTIVO | RECHAZADO
    quality_notes = Column(Text)
    trained_at = Column(DateTime, default=utcnow, nullable=False)

    dataset = relationship("Dataset", back_populates="model_versions")
    predictions = relationship("Prediction", back_populates="model_version")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    warehouse_block = Column(String(1), nullable=False)
    mode_of_shipment = Column(String(10), nullable=False)
    customer_care_calls = Column(Integer, nullable=False)
    customer_rating = Column(Integer, nullable=False)
    cost_of_the_product = Column(Float, nullable=False)
    prior_purchases = Column(Integer, nullable=False)
    product_importance = Column(String(10), nullable=False)
    gender = Column(String(1), nullable=False)
    discount_offered = Column(Float, nullable=False)
    weight_in_gms = Column(Float, nullable=False)
    predicted_class = Column(Integer, nullable=False)
    predicted_label = Column(String(20), nullable=False)
    probability_delay = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    model_version = relationship("ModelVersion", back_populates="predictions")


class RetrainRequest(Base):
    __tablename__ = "retrain_requests"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    algorithm = Column(String(100), nullable=False, default="auto")
    status = Column(String(20), nullable=False)   # COMPLETADO | RECHAZADO | ERROR
    resulting_model_id = Column(Integer, ForeignKey("model_versions.id"))
    message = Column(Text)
    requested_at = Column(DateTime, default=utcnow, nullable=False)
    finished_at = Column(DateTime)
