-- =====================================================================
-- Shipping Delay AI – Script de creación de la base de datos
-- Compatible con PostgreSQL 13+ y SQLite 3 (ver notas al final).
-- La aplicación también crea estas tablas automáticamente al iniciar
-- (SQLAlchemy: Base.metadata.create_all).
-- =====================================================================

-- PostgreSQL:  CREATE DATABASE shipping_ai;   \c shipping_ai

DROP TABLE IF EXISTS retrain_requests;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS model_versions;
DROP TABLE IF EXISTS datasets;

-- ---------------------------------------------------------------------
-- Archivos de entrenamiento subidos (incluye el dataset base de Kaggle)
-- ---------------------------------------------------------------------
CREATE TABLE datasets (
    id               INTEGER PRIMARY KEY,          -- PostgreSQL: SERIAL PRIMARY KEY
    filename         VARCHAR(255) NOT NULL,
    storage_path     VARCHAR(500) NOT NULL,
    row_count        INTEGER      NOT NULL CHECK (row_count >= 0),
    class_balance    TEXT,                         -- JSON {"0":0.40,"1":0.60}
    validation_notes TEXT,                         -- JSON lista de observaciones
    uploaded_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- Versiones del modelo entrenadas (registro de modelos / model registry)
-- ---------------------------------------------------------------------
CREATE TABLE model_versions (
    id                 INTEGER PRIMARY KEY,        -- PostgreSQL: SERIAL PRIMARY KEY
    version            VARCHAR(50)  NOT NULL UNIQUE,
    algorithm          VARCHAR(100) NOT NULL,
    hyperparameters    TEXT,                       -- JSON
    dataset_id         INTEGER      NOT NULL REFERENCES datasets(id),
    train_rows         INTEGER,
    test_rows          INTEGER,
    accuracy           REAL,                       -- PostgreSQL: DOUBLE PRECISION
    "precision"        REAL,
    recall             REAL,
    f1_score           REAL,
    roc_auc            REAL,
    cv_roc_auc         REAL,
    confusion_matrix   TEXT,                       -- JSON {"tn","fp","fn","tp"}
    feature_importance TEXT,                       -- JSON
    comparison         TEXT,                       -- JSON (todos los candidatos)
    artifact_path      VARCHAR(500) NOT NULL,
    status             VARCHAR(20)  NOT NULL
                       CHECK (status IN ('ACTIVO','INACTIVO','RECHAZADO')),
    quality_notes      TEXT,
    trained_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_model_versions_status ON model_versions(status);

-- ---------------------------------------------------------------------
-- Historial de predicciones: datos enviados + resultado
-- ---------------------------------------------------------------------
CREATE TABLE predictions (
    id                  INTEGER PRIMARY KEY,       -- PostgreSQL: SERIAL PRIMARY KEY
    model_version_id    INTEGER     NOT NULL REFERENCES model_versions(id),
    warehouse_block     VARCHAR(1)  NOT NULL CHECK (warehouse_block IN ('A','B','C','D','F')),
    mode_of_shipment    VARCHAR(10) NOT NULL CHECK (mode_of_shipment IN ('Flight','Ship','Road')),
    customer_care_calls INTEGER     NOT NULL,
    customer_rating     INTEGER     NOT NULL CHECK (customer_rating BETWEEN 1 AND 5),
    cost_of_the_product REAL        NOT NULL,
    prior_purchases     INTEGER     NOT NULL,
    product_importance  VARCHAR(10) NOT NULL CHECK (product_importance IN ('low','medium','high')),
    gender              VARCHAR(1)  NOT NULL CHECK (gender IN ('F','M')),
    discount_offered    REAL        NOT NULL,
    weight_in_gms       REAL        NOT NULL,
    predicted_class     INTEGER     NOT NULL CHECK (predicted_class IN (0,1)),
    predicted_label     VARCHAR(20) NOT NULL,
    probability_delay   REAL        NOT NULL CHECK (probability_delay BETWEEN 0 AND 1),
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_predictions_created_at ON predictions(created_at);
CREATE INDEX ix_predictions_model ON predictions(model_version_id);

-- ---------------------------------------------------------------------
-- Solicitudes de reentrenamiento (trazabilidad del ciclo de vida)
-- ---------------------------------------------------------------------
CREATE TABLE retrain_requests (
    id                 INTEGER PRIMARY KEY,        -- PostgreSQL: SERIAL PRIMARY KEY
    dataset_id         INTEGER      NOT NULL REFERENCES datasets(id),
    algorithm          VARCHAR(100) NOT NULL DEFAULT 'auto',
    status             VARCHAR(20)  NOT NULL
                       CHECK (status IN ('EN_PROCESO','COMPLETADO','RECHAZADO','ERROR')),
    resulting_model_id INTEGER REFERENCES model_versions(id),
    message            TEXT,
    requested_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at        TIMESTAMP
);

-- Notas:
--  * SQLite:     sqlite3 shipping_ai.db < db/schema.sql
--  * PostgreSQL: reemplazar "INTEGER PRIMARY KEY" por "SERIAL PRIMARY KEY" y
--                "REAL" por "DOUBLE PRECISION"; luego  psql -d shipping_ai -f db/schema.sql
--                y exportar DATABASE_URL=postgresql+psycopg2://user:pass@host/shipping_ai
