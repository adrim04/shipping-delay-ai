# Shipping Delay AI 🚚

Servicio de IA que predice si un envío de e-commerce **llegará con retraso**, entrenado con el dataset
[E-Commerce Shipping Data](https://www.kaggle.com/datasets/prachi13/customer-analytics) (Kaggle) y
siguiendo la metodología **CRISP-ML(Q)**.

| Componente | Tecnología |
|---|---|
| Modelo | scikit-learn (Gradient Boosting / Random Forest / Regresión Logística, selección automática) |
| API REST | FastAPI + Swagger (OpenAPI 3) |
| Base de datos | SQLite (por defecto) o PostgreSQL vía SQLAlchemy |
| Cliente web | HTML + CSS + JavaScript (sin frameworks) |
| Calidad | pytest, ruff, GitHub Actions, revisión de PR con IA (CodeRabbit / Copilot) |

## Tipo de problema
**Clasificación binaria supervisada.** Variable objetivo `Reached.on.Time_Y.N`:
`0` = llegó a tiempo · `1` = **no** llegó a tiempo (retraso).

## Resultado del modelo (conjunto de prueba, 2.200 envíos)
| Métrica | Valor | Umbral de calidad |
|---|---|---|
| ROC-AUC | 0.759 | ≥ 0.70 ✅ |
| Accuracy | 0.678 | ≥ 0.65 ✅ |
| F1 | 0.643 | ≥ 0.60 ✅ |
| Precision (retraso) | 0.952 | — |
| Recall (retraso) | 0.485 | — |

## Estructura
```
backend/
  app/            main.py (API) · services.py · models.py (ORM) · schemas.py · ml/pipeline.py
  scripts/        train.py (CRISP-ML(Q) con EDA y figuras) · export_openapi.py
  db/schema.sql   script de creación de la base de datos
  data/           Train.csv (dataset) · ejemplo_dataset_actualizado.csv (para probar reentrenamiento)
  tests/          pruebas de integración de la API
frontend/         cliente web (index.html, app.js, styles.css)
docs/             openapi.yaml/json · swagger.html · diagrama_bd.png/.mmd · cronograma_gantt.png
                  crisp_ml/ (figuras y reportes del entrenamiento) · capturas/
```

## Cómo ejecutar
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.train          # (opcional) EDA + entrenamiento con reporte por fases
uvicorn app.main:app --reload
```
- Cliente web: http://localhost:8000/  
- Swagger UI: http://localhost:8000/docs · ReDoc: http://localhost:8000/redoc  
- La primera vez, el servicio crea la base de datos y entrena el modelo inicial (~30 s).

Para usar PostgreSQL: `export DATABASE_URL=postgresql+psycopg2://usuario:clave@localhost:5432/shipping_ai`
(y `pip install psycopg2-binary`).

## Endpoints (`/api/v1`)
| Método | Ruta | Requisito |
|---|---|---|
| POST | `/predictions` | a) Enviar datos y obtener la predicción |
| GET | `/predictions` · `/predictions/{id}` | b) Historial de predicciones (datos + resultado) |
| GET | `/metrics` · `/models` | c) Métricas del modelo activo y de todas las versiones |
| POST | `/retrain` | d) Reentrenar con información actualizada |
| POST | `/datasets` · GET `/datasets` | e) Enviar el archivo de entrenamiento |
| GET | `/health` | Estado del servicio |

Ejemplo:
```bash
curl -X POST http://localhost:8000/api/v1/predictions -H "Content-Type: application/json" -d '{
  "warehouse_block":"F","mode_of_shipment":"Ship","customer_care_calls":4,"customer_rating":3,
  "cost_of_the_product":210,"prior_purchases":3,"product_importance":"medium","gender":"F",
  "discount_offered":45,"weight_in_gms":1500}'
```

## Pruebas
```bash
cd backend && ruff check . && pytest -q
```
