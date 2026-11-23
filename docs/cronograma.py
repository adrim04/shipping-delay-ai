"""Genera el diagrama de Gantt del cronograma CRISP-ML(Q)."""
from datetime import date, timedelta
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

T = [  # (fase, tarea, inicio, días)
 ("1. Negocio y datos", "Definir objetivo, criterios de éxito y umbrales", date(2026,11,23), 2),
 ("1. Negocio y datos", "Selección del dataset y EDA", date(2026,11,24), 3),
 ("2. Ingeniería de datos", "Validación, limpieza y pipeline de preprocesamiento", date(2026,11,26), 3),
 ("3. Ingeniería del modelo", "Entrenar candidatos + GridSearch (CV 5-fold)", date(2026,11,29), 4),
 ("4. Evaluación", "Métricas en test, compuerta de calidad, selección", date(2026,12,2), 2),
 ("5. Despliegue", "Base de datos + API REST (FastAPI) + Swagger", date(2026,12,3), 5),
 ("5. Despliegue", "Interfaz web cliente", date(2026,12,7), 4),
 ("5. Despliegue", "Pruebas, CI en GitHub y revisión de PR con IA", date(2026,12,10), 3),
 ("6. Monitoreo y mantenimiento", "Historial, versionado y reentrenamiento", date(2026,12,11), 3),
 ("Cierre", "Documento, video y entrega", date(2026,12,13), 3),
]
colors = {"1":"#2E7D6B","2":"#4F9D8A","3":"#D9822B","4":"#B9473A","5":"#3E5C76","6":"#7A6C9E","C":"#7d8585"}
fig, ax = plt.subplots(figsize=(12, 5))
for i, (f, t, s, d) in enumerate(T):
    ax.barh(i, d, left=mdates.date2num(s), color=colors[f[0]], height=.6)
    ax.text(mdates.date2num(s + timedelta(days=d)) + .2, i, f"{d} d", va="center", fontsize=8, color="#555")
ax.set_yticks(range(len(T))); ax.set_yticklabels([f"{f} · {t}" for f, t, *_ in T], fontsize=8.5)
ax.invert_yaxis(); ax.xaxis_date(); ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
ax.xaxis.set_major_locator(mdates.DayLocator(interval=2)); ax.grid(axis="x", alpha=.3)
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.set_title("Cronograma de trabajo basado en CRISP-ML(Q)", loc="left", fontsize=12)
fig.tight_layout(); fig.savefig("docs/cronograma_gantt.png", dpi=140)
