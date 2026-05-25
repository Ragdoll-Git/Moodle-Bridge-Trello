"""
MoodleAPI-Bridge — Rutas stub para Trello API.

Endpoints preparados para futuras integraciones con Trello.
Por ahora devuelven respuestas 501 (Not Implemented).
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("moodle-bridge.routes.trello")

router = APIRouter(prefix="/api/trello", tags=["Trello (Próximamente)"])


class StubResponse(BaseModel):
    success: bool = False
    message: str = ""
    status: str = "not_implemented"


@router.post("/sync")
async def sync_trello():
    """
    [PRÓXIMAMENTE] Crea tarjetas en Trello a partir de las tareas de Moodle.

    Funcionalidad planificada:
    - Crear tarjetas por cada tarea/actividad
    - Sincronizar fechas de entrega
    - Organización por materia en boards/listas
    """
    return StubResponse(
        message="Integración con Trello en desarrollo. "
        "Configurá TRELLO_API_KEY y TRELLO_TOKEN en .env cuando esté listo.",
    )


@router.get("/boards")
async def list_boards():
    """
    [PRÓXIMAMENTE] Lista los boards de Trello del usuario.
    """
    return StubResponse(
        message="Trello API no configurada. Endpoint reservado para integración futura.",
    )


@router.get("/status")
async def trello_status():
    """Estado de la integración con Trello"""
    return StubResponse(
        message="Trello API no configurada. Endpoint reservado para integración futura.",
    )
