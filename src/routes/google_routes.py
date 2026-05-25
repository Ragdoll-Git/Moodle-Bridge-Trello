"""
MoodleAPI-Bridge — Rutas stub para Google APIs.

Endpoints preparados para futuras integraciones con Google Drive,
Google Calendar, etc. Por ahora devuelven respuestas 501 (Not Implemented).
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("moodle-bridge.routes.google")

router = APIRouter(prefix="/api/google", tags=["Google (Próximamente)"])


class StubResponse(BaseModel):
    success: bool = False
    message: str = ""
    status: str = "not_implemented"


@router.post("/sync")
async def sync_google_drive():
    """
    [PRÓXIMAMENTE] Sincroniza recursos de Moodle con Google Drive.

    Funcionalidad planificada:
    - Subir archivos descargados a una carpeta de Drive
    - Sincronización incremental
    - Organización por materia
    """
    return StubResponse(
        message="Integración con Google Drive en desarrollo. "
        "Configurá GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en .env cuando esté listo.",
    )


@router.get("/status")
async def google_status():
    """Estado de la integración con Google"""
    return StubResponse(
        message="Google API no configurada. Endpoint reservado para integración futura.",
    )
