"""Run with the project virtualenv from the repository root."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.main import app

(root / "apps/web/lib/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
