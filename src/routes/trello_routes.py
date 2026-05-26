"""
MoodleAPI-Bridge — Rutas de la API de Trello.

Endpoints REST para interactuar con Trello: listar boards,
sincronizar tareas desde Moodle y verificar el estado de la conexión.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..services.bridge import bridge_service
from ..trello.models import TrelloSyncResult

logger = logging.getLogger("moodle-bridge.routes.trello")

router = APIRouter(prefix="/api/trello", tags=["Trello"])


# ============================================================
# Request models
# ============================================================

class SyncRequest(BaseModel):
    """Opciones para la sincronización Moodle → Trello"""
    board_name: Optional[str] = None
    course_ids: Optional[list[int]] = None


# ============================================================
# Endpoints
# ============================================================

@router.post("/sync", response_model=TrelloSyncResult)
async def sync_trello(body: Optional[SyncRequest] = None):
    """
    Sincroniza las tareas de Moodle al board de Trello.

    **Comportamiento:**
    - Busca el board por nombre (default: "Facu")
    - Crea una lista por cada curso
    - Crea tarjetas por cada assignment/foro
    - Si la tarjeta ya existe (por nombre), la actualiza

    **Opciones en el body (todas opcionales):**
    - `board_name`: Nombre del board de Trello (default: "Facu")
    - `course_ids`: Lista de IDs de cursos a sincronizar (default: todos)

    **Requiere:**
    - Autenticación con Moodle (POST /api/moodle/auth)
    - TRELLO_API_KEY y TRELLO_TOKEN configurados en .env
    """
    board_name = body.board_name if body else None
    course_ids = body.course_ids if body else None

    logger.info(
        f"Petición de sincronización Trello "
        f"(board={board_name or 'default'}, courses={course_ids or 'todos'})"
    )

    return bridge_service.trello_sync_assignments(
        board_name=board_name,
        course_ids=course_ids,
    )


@router.get("/boards")
async def list_boards():
    """
    Lista los boards de Trello del usuario autenticado.

    Útil para verificar la conexión y encontrar el board_id/nombre correcto.
    """
    logger.info("Petición de listado de boards Trello")
    return bridge_service.trello_get_boards()


@router.get("/status")
async def trello_status():
    """
    Estado de la integración con Trello.

    Verifica si las credenciales están configuradas y si la conexión funciona.
    """
    return bridge_service.trello_get_status()
