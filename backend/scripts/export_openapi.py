"""Exporta el documento Swagger/OpenAPI a docs/openapi.json y docs/openapi.yaml.
Uso (desde backend/):  python -m scripts.export_openapi
"""
import json
from pathlib import Path

import yaml

from app.main import app

DOCS = Path(__file__).resolve().parents[2] / "docs"
spec = app.openapi()
(DOCS / "openapi.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False))
(DOCS / "openapi.yaml").write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False))
print("OpenAPI exportado en", DOCS)
