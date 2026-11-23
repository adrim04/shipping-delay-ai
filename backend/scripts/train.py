"""
Entrenamiento inicial siguiendo CRISP-ML(Q) – genera reportes y figuras en ../docs/.
Uso (desde backend/):  python -m scripts.train
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.config import ARTIFACTS_DIR, BASE_DATASET
from app.ml import pipeline as ml

DOCS = Path(__file__).resolve().parents[2] / "docs" / "crisp_ml"
DOCS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})
C0, C1 = "#2E7D6B", "#D9822B"


def phase(title):
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


# ---------- Fase 1: Comprensión del negocio y de los datos
phase("FASE 1 – Comprensión del negocio y de los datos")
df = ml.load_dataset(BASE_DATASET)
print(f"Dimensiones: {df.shape}")
print(df.head())
desc = df.describe().T.round(2)
print(desc)
desc.to_csv(DOCS / "estadisticas_descriptivas.csv")

fig, ax = plt.subplots(figsize=(5, 3.2))
vc = df[ml.TARGET].value_counts().sort_index()
ax.bar(["A tiempo (0)", "Con retraso (1)"], vc.values, color=[C0, C1])
for i, v in enumerate(vc.values):
    ax.text(i, v + 80, f"{v} ({v/len(df):.1%})", ha="center")
ax.set_title("Distribución de la variable objetivo"); ax.set_ylabel("Envíos")
fig.tight_layout(); fig.savefig(DOCS / "01_distribucion_objetivo.png"); plt.close(fig)

fig, axes = plt.subplots(2, 3, figsize=(11, 6))
for ax, col in zip(axes.ravel(), ml.NUMERIC):
    for cls, color in [(0, C0), (1, C1)]:
        ax.hist(df[df[ml.TARGET] == cls][col], bins=25, alpha=.6, color=color,
                label=ml.LABELS[cls])
    ax.set_title(col, fontsize=10)
axes[0, 0].legend(fontsize=8)
fig.suptitle("Variables numéricas por clase"); fig.tight_layout()
fig.savefig(DOCS / "02_numericas_por_clase.png"); plt.close(fig)

fig, axes = plt.subplots(1, 4, figsize=(13, 3.2))
for ax, col in zip(axes, ml.CATEGORICAL):
    rate = df.groupby(col)[ml.TARGET].mean().sort_values()
    ax.barh(rate.index.astype(str), rate.values, color=C1)
    ax.set_xlim(0, 1); ax.set_title(f"% retraso por {col}", fontsize=10)
fig.tight_layout(); fig.savefig(DOCS / "03_retraso_por_categoria.png"); plt.close(fig)

corr = df[ml.NUMERIC + [ml.TARGET]].corr()[ml.TARGET].drop(ml.TARGET).sort_values()
print("\nCorrelación con el objetivo:\n", corr.round(3))

# ---------- Fase 2: Ingeniería de datos (calidad)
phase("FASE 2 – Ingeniería de datos y aseguramiento de calidad")
report = ml.validate_dataset(df)
print(json.dumps(report, indent=2, ensure_ascii=False))
clean = ml.clean_dataset(df)
print(f"Filas después de limpieza: {len(clean)}")

# ---------- Fase 3: Ingeniería del modelo
phase("FASE 3 – Ingeniería del modelo (GridSearchCV, 5 folds, ROC-AUC)")
result = ml.train_and_select(df)
comp = pd.DataFrame(result.comparison)
print(comp.to_string(index=False))
comp.to_csv(DOCS / "comparacion_modelos.csv", index=False)

fig, ax = plt.subplots(figsize=(7, 3.4))
x = range(len(comp)); w = .2
for i, (m, c) in enumerate([("accuracy", "#8DA0CB"), ("f1", "#66C2A5"),
                            ("roc_auc", C1), ("cv_roc_auc", C0)]):
    ax.bar([j + (i - 1.5) * w for j in x], comp[m], w, label=m, color=c)
ax.set_xticks(list(x)); ax.set_xticklabels(comp["algorithm"]); ax.set_ylim(.5, 1)
ax.axhline(.70, ls="--", color="grey", lw=1); ax.legend(fontsize=8, ncol=4)
ax.set_title("Comparación de modelos candidatos")
fig.tight_layout(); fig.savefig(DOCS / "04_comparacion_modelos.png"); plt.close(fig)

# ---------- Fase 4: Evaluación
phase("FASE 4 – Evaluación y compuerta de calidad")
print(f"Modelo elegido: {result.algorithm} {result.params}")
print(json.dumps(result.metrics, indent=2))
ok, fails = ml.passes_quality_gate(result.metrics)
print("Compuerta de calidad:", "APROBADO" if ok else f"RECHAZADO {fails}")

cm = result.metrics["confusion_matrix"]
fig, ax = plt.subplots(figsize=(3.8, 3.4))
mat = [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]]
ax.imshow(mat, cmap="Greens")
for i in range(2):
    for j in range(2):
        ax.text(j, i, mat[i][j], ha="center", va="center", fontsize=13)
ax.set_xticks([0, 1]); ax.set_xticklabels(["A tiempo", "Retraso"])
ax.set_yticks([0, 1]); ax.set_yticklabels(["A tiempo", "Retraso"])
ax.set_xlabel("Predicho"); ax.set_ylabel("Real"); ax.set_title("Matriz de confusión (test)")
fig.tight_layout(); fig.savefig(DOCS / "05_matriz_confusion.png"); plt.close(fig)

fi = ml.feature_importance(result.pipeline)[:10]
fig, ax = plt.subplots(figsize=(6, 3.6))
ax.barh([f["feature"] for f in fi][::-1], [f["importance"] for f in fi][::-1], color=C0)
ax.set_title("Importancia de variables (top 10)")
fig.tight_layout(); fig.savefig(DOCS / "06_importancia_variables.png"); plt.close(fig)

# ---------- Fase 5: Despliegue (artefacto)
phase("FASE 5 – Empaquetado del artefacto para despliegue")
path = ml.save_model(result, ARTIFACTS_DIR, "v0-baseline")
print(f"Modelo guardado en {path}")
(DOCS / "resumen_entrenamiento.json").write_text(json.dumps({
    "algorithm": result.algorithm, "params": result.params, "metrics": result.metrics,
    "quality_gate": {"passed": ok, "failures": fails}, "feature_importance": fi,
    "train_rows": result.train_rows, "test_rows": result.test_rows}, indent=2))
