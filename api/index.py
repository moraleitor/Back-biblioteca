"""Modo Vercel (demo): todos los servicios en UN solo proceso, conectados en memoria.

Limitaciones del entorno serverless: los datos viven en /tmp (se pierden al reiniciar
la función) y no hay Tesseract, así que /api/scan responde 503 (OCR no disponible).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATA_DIR", "/tmp/biblioteca-data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

from common import registry  # noqa: E402
from services.ai.app import create_app as ai_app  # noqa: E402
from services.auth.app import create_app as auth_app  # noqa: E402
from services.backup.app import create_app as backup_app  # noqa: E402
from services.gateway.app import create_app as gateway_app  # noqa: E402
from services.library.app import create_app as library_app  # noqa: E402
from services.notes.app import create_app as notes_app  # noqa: E402
from services.ocr.app import create_app as ocr_app  # noqa: E402

registry.use_apps({
    "auth": auth_app(), "library": library_app(), "notes": notes_app(),
    "ocr": ocr_app(), "ai": ai_app(), "backup": backup_app(),
})
app = gateway_app()
