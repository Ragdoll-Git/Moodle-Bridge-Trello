"""
MoodleAPI-Bridge — Servicio Bridge.

Capa de servicio que gestiona el estado global de las conexiones
a Moodle y futuros servicios (Google, Trello). Actúa como punto
central de coordinación entre las rutas API y los clientes.
"""

import logging
import time
from datetime import datetime
from typing import Optional

from ..config import settings
from ..moodle.client import MoodleClient
from ..moodle.auth import MoodleAuthError
from ..moodle.models import (
    SiteInfo,
    Course,
    CourseSection,
    BridgeStatus,
    AuthResponse,
    CoursesResponse,
    CourseContentsResponse,
)

logger = logging.getLogger("moodle-bridge.service")


class BridgeService:
    """
    Servicio central del bridge. Mantiene el estado de las conexiones
    y proporciona métodos de alto nivel para las rutas API.
    """

    def __init__(self):
        self._start_time = time.time()
        self._moodle_client: Optional[MoodleClient] = None
        self._last_auth_time: Optional[datetime] = None
        self._error_log: list[dict] = []

    # ============================================================
    # Estado
    # ============================================================

    def get_status(self) -> BridgeStatus:
        """Devuelve el estado actual del servicio"""
        return BridgeStatus(
            service="MoodleAPI-Bridge",
            status="running",
            version="0.1.0",
            timestamp=datetime.now(),
            moodle_configured=settings.is_moodle_configured,
            moodle_connected=self._moodle_client is not None and self._moodle_client.is_authenticated,
            google_configured=settings.is_google_configured,
            trello_configured=settings.is_trello_configured,
            uptime_seconds=round(time.time() - self._start_time, 1),
        )

    @property
    def recent_errors(self) -> list[dict]:
        """Últimos errores registrados (máx 50)"""
        return self._error_log[-50:]

    def _log_error(self, source: str, error: str):
        """Registra un error en el log interno"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "error": error,
        }
        self._error_log.append(entry)
        # Mantener máximo 100 entradas
        if len(self._error_log) > 100:
            self._error_log = self._error_log[-50:]

    # ============================================================
    # Moodle
    # ============================================================

    def moodle_authenticate(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> AuthResponse:
        """
        Autentica con Moodle usando las credenciales proporcionadas
        o las del .env.

        Returns:
            AuthResponse con el resultado
        """
        user = username or settings.moodle_username
        pwd = password or settings.moodle_password

        if not user or not pwd:
            return AuthResponse(
                success=False,
                message="Credenciales no configuradas",
                error="Configurá MOODLE_USERNAME y MOODLE_PASSWORD en el archivo .env",
            )

        try:
            # Crear nuevo cliente
            if self._moodle_client:
                self._moodle_client.close()

            self._moodle_client = MoodleClient(
                base_url=settings.moodle_base_url,
                request_delay=settings.request_delay,
                max_retries=settings.max_retries,
            )

            site_info = self._moodle_client.authenticate(user, pwd)
            self._last_auth_time = datetime.now()

            logger.info(
                f"Autenticación exitosa: {site_info.fullname} "
                f"(userid: {site_info.userid})"
            )

            return AuthResponse(
                success=True,
                message=f"Autenticado como {site_info.fullname}",
                site_info=site_info,
            )

        except MoodleAuthError as e:
            error_msg = str(e)
            logger.error(f"Error de autenticación: {error_msg}")
            self._log_error("moodle_auth", error_msg)
            return AuthResponse(
                success=False,
                message="Error de autenticación",
                error=error_msg,
            )
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._log_error("moodle_auth", error_msg)
            return AuthResponse(
                success=False,
                message="Error inesperado",
                error=error_msg,
            )

    def moodle_get_courses(self) -> CoursesResponse:
        """
        Obtiene los cursos del usuario autenticado.

        Returns:
            CoursesResponse con la lista de cursos
        """
        if not self._moodle_client or not self._moodle_client.is_authenticated:
            return CoursesResponse(
                success=False,
                message="No autenticado",
                error="Primero autenticate con POST /api/moodle/auth",
            )

        try:
            courses = self._moodle_client.get_user_courses()

            return CoursesResponse(
                success=True,
                message=f"Se encontraron {len(courses)} cursos",
                total_courses=len(courses),
                courses=courses,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error al obtener cursos: {error_msg}")
            self._log_error("moodle_courses", error_msg)
            return CoursesResponse(
                success=False,
                message="Error al obtener cursos",
                error=error_msg,
            )

    def moodle_get_course_contents(self, course_id: int) -> CourseContentsResponse:
        """
        Obtiene los contenidos (secciones, módulos, archivos) de un curso.

        Args:
            course_id: ID del curso en Moodle

        Returns:
            CourseContentsResponse con las secciones y archivos
        """
        if not self._moodle_client or not self._moodle_client.is_authenticated:
            return CourseContentsResponse(
                success=False,
                message="No autenticado",
                course_id=course_id,
                error="Primero autenticate con POST /api/moodle/auth",
            )

        try:
            sections = self._moodle_client.get_course_contents(course_id)

            total_files = sum(
                m.file_count
                for s in sections
                for m in s.modules
            )

            # Intentar obtener el nombre del curso
            course_name = ""
            try:
                courses = self._moodle_client.get_user_courses()
                matching = [c for c in courses if c.id == course_id]
                if matching:
                    course_name = matching[0].fullname
            except Exception:
                pass  # No crítico, continuamos sin nombre

            return CourseContentsResponse(
                success=True,
                message=f"Curso {course_id}: {len(sections)} secciones, {total_files} archivos",
                course_id=course_id,
                course_name=course_name,
                total_sections=len(sections),
                total_files=total_files,
                sections=sections,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error al obtener contenidos del curso {course_id}: {error_msg}")
            self._log_error("moodle_contents", error_msg)
            return CourseContentsResponse(
                success=False,
                message=f"Error al obtener contenidos del curso {course_id}",
                course_id=course_id,
                error=error_msg,
            )

    # ============================================================
    # Cleanup
    # ============================================================

    def shutdown(self):
        """Cierra todas las conexiones"""
        if self._moodle_client:
            self._moodle_client.close()
            self._moodle_client = None
        logger.info("Bridge service shut down")


# Instancia global del servicio
bridge_service = BridgeService()
