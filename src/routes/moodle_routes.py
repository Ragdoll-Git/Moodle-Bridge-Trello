"""
MoodleAPI-Bridge — Rutas de la API de Moodle.

Endpoints REST para interactuar con Moodle a través del bridge.
Todos los endpoints devuelven respuestas JSON tipadas.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..services.bridge import bridge_service
from ..moodle.models import AuthResponse, CoursesResponse, CourseContentsResponse, AssignmentsResponse

logger = logging.getLogger("moodle-bridge.routes.moodle")

router = APIRouter(prefix="/api/moodle", tags=["Moodle"])


# ============================================================
# Request models
# ============================================================

class AuthRequest(BaseModel):
    """Cuerpo de la petición de autenticación (opcional, usa .env si no se envía)"""
    username: Optional[str] = None
    password: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================

@router.post("/auth", response_model=AuthResponse)
async def authenticate(body: Optional[AuthRequest] = None):
    """
    Autentica con Moodle.

    Si no se envían credenciales en el body, usa las del archivo .env.
    Devuelve información del sitio y del usuario autenticado.
    """
    username = body.username if body else None
    password = body.password if body else None

    logger.info("Petición de autenticación recibida")
    result = bridge_service.moodle_authenticate(username, password)

    if result.success:
        logger.info(f"Auth exitosa: {result.site_info.fullname if result.site_info else 'N/A'}")
    else:
        logger.warning(f"Auth fallida: {result.error}")

    return result


@router.get("/courses", response_model=CoursesResponse)
async def get_courses():
    """
    Lista los cursos del usuario autenticado.

    Requiere autenticación previa via POST /api/moodle/auth.
    Devuelve la lista completa de cursos con sus IDs, nombres y metadata.
    """
    logger.info("Petición de listado de cursos")
    return bridge_service.moodle_get_courses()


@router.get("/courses/{course_id}/contents", response_model=CourseContentsResponse)
async def get_course_contents(course_id: int):
    """
    Obtiene las secciones y recursos de un curso específico.

    Devuelve la estructura completa: secciones → módulos → archivos.
    Cada archivo incluye su URL de descarga y metadatos.
    """
    logger.info(f"Petición de contenidos del curso {course_id}")
    return bridge_service.moodle_get_course_contents(course_id)


@router.get("/assignments", response_model=AssignmentsResponse)
async def get_assignments(
    course_id: Optional[int] = Query(None, description="Filtrar por ID de curso"),
):
    """
    Obtiene las tareas (assignments) y foros de todos los cursos o de uno específico.

    Combina datos de:
    - `mod_assign_get_assignments` — tareas con fechas de entrega
    - `core_course_get_contents` — actividades visibles y ocultas (assign + forum)

    Cada assignment incluye: nombre, fecha de entrega, fecha límite, descripción.
    Las actividades incluyen si están ocultas (`uservisible: false`).
    """
    logger.info(f"Petición de assignments (course_id={course_id})")
    course_ids = [course_id] if course_id else None
    return bridge_service.moodle_get_assignments(course_ids)
