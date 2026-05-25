"""
MoodleAPI-Bridge — Cliente de la API REST de Moodle.

Cliente con rate limiting automático, reintentos con backoff exponencial
y métodos tipados para las funciones principales del Web Service de Moodle.
"""

import logging
import time
import requests
from typing import Any, Optional

from .auth import MoodleAuth, MoodleAuthError
from .models import (
    Course,
    CourseSection,
    CourseModule,
    ModuleContent,
    MoodleError,
    SiteInfo,
)

logger = logging.getLogger("moodle-bridge.client")


class MoodleAPIError(Exception):
    """Error en una llamada a la API de Moodle"""

    def __init__(self, message: str, wsfunction: str = "", errorcode: Optional[str] = None):
        self.wsfunction = wsfunction
        self.errorcode = errorcode
        super().__init__(message)


class MoodleClient:
    """
    Cliente de la API REST de Moodle con rate limiting y reintentos.

    Uso:
        client = MoodleClient(base_url, request_delay=1.5)
        client.authenticate(username, password)
        courses = client.get_user_courses()
    """

    def __init__(
        self,
        base_url: str,
        request_delay: float = 1.5,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/webservice/rest/server.php"
        self.request_delay = request_delay
        self.max_retries = max_retries

        self._auth = MoodleAuth(base_url)
        self._token: Optional[str] = None
        self._userid: Optional[int] = None
        self._site_info: Optional[SiteInfo] = None
        self._last_request_time: float = 0

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "MoodleAPI-Bridge/0.1.0 (Student Resource Organizer)"
        })

    # ============================================================
    # Propiedades
    # ============================================================

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    @property
    def token(self) -> Optional[str]:
        return self._token

    @property
    def userid(self) -> Optional[int]:
        return self._userid

    @property
    def site_info(self) -> Optional[SiteInfo]:
        return self._site_info

    # ============================================================
    # Autenticación
    # ============================================================

    def authenticate(self, username: str, password: str) -> SiteInfo:
        """
        Autentica con Moodle y almacena el token internamente.

        Returns:
            SiteInfo con los datos del usuario y sitio

        Raises:
            MoodleAuthError: Si la autenticación falla
        """
        token, site_info = self._auth.authenticate(username, password)
        self._token = token
        self._userid = site_info.userid
        self._site_info = site_info
        return site_info

    # ============================================================
    # API de Moodle: Cursos
    # ============================================================

    def get_user_courses(self, userid: Optional[int] = None) -> list[Course]:
        """
        Obtiene la lista de cursos en los que el usuario está matriculado.
        Usa core_enrol_get_users_courses.

        Args:
            userid: ID del usuario. Si no se pasa, usa el del usuario autenticado.

        Returns:
            Lista de Course
        """
        uid = userid or self._userid
        if uid is None:
            raise MoodleAPIError(
                "No hay userid disponible. ¿Te autenticaste primero?",
                wsfunction="core_enrol_get_users_courses",
            )

        logger.info(f"Obteniendo cursos del usuario {uid}...")

        data = self._call("core_enrol_get_users_courses", {"userid": uid})

        if isinstance(data, dict) and ("exception" in data or "errorcode" in data):
            error = MoodleError(**data)
            raise MoodleAPIError(
                f"Error al obtener cursos: {error.message or error.error}",
                wsfunction="core_enrol_get_users_courses",
                errorcode=error.errorcode,
            )

        if not isinstance(data, list):
            raise MoodleAPIError(
                f"Respuesta inesperada de Moodle (se esperaba una lista): {str(data)[:200]}",
                wsfunction="core_enrol_get_users_courses",
            )

        courses = [Course(**c) for c in data]
        logger.info(f"Se encontraron {len(courses)} cursos")

        for course in courses:
            logger.debug(f"  [{course.id}] {course.fullname}")

        return courses

    def get_course_contents(self, course_id: int) -> list[CourseSection]:
        """
        Obtiene las secciones y módulos de un curso.
        Usa core_course_get_contents.

        Args:
            course_id: ID del curso

        Returns:
            Lista de CourseSection con sus módulos y archivos
        """
        logger.info(f"Obteniendo contenidos del curso {course_id}...")

        data = self._call("core_course_get_contents", {"courseid": course_id})

        if isinstance(data, dict) and ("exception" in data or "errorcode" in data):
            error = MoodleError(**data)
            raise MoodleAPIError(
                f"Error al obtener contenidos del curso {course_id}: {error.message or error.error}",
                wsfunction="core_course_get_contents",
                errorcode=error.errorcode,
            )

        if not isinstance(data, list):
            raise MoodleAPIError(
                f"Respuesta inesperada de Moodle: {str(data)[:200]}",
                wsfunction="core_course_get_contents",
            )

        sections = [CourseSection(**s) for s in data]

        # Contar archivos
        total_files = sum(
            m.file_count
            for s in sections
            for m in s.modules
        )
        logger.info(f"Curso {course_id}: {len(sections)} secciones, {total_files} archivos")

        return sections

    # ============================================================
    # Llamada genérica a la API con rate limiting
    # ============================================================

    def _call(self, wsfunction: str, params: Optional[dict] = None) -> Any:
        """
        Realiza una llamada a la API REST de Moodle con rate limiting
        y reintentos automáticos.

        Args:
            wsfunction: Nombre de la función del Web Service
            params: Parámetros adicionales para la función

        Returns:
            Respuesta JSON parseada
        """
        if not self._token:
            raise MoodleAPIError(
                "No autenticado. Llamá a authenticate() primero.",
                wsfunction=wsfunction,
            )

        # Rate limiting: esperar si es necesario
        self._rate_limit()

        # Construir parámetros
        full_params = {
            "wstoken": self._token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }
        if params:
            full_params.update(params)

        # Intentar con reintentos
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    f"API call [{attempt}/{self.max_retries}]: {wsfunction} "
                    f"params={params}"
                )

                response = self._session.get(
                    self.api_url,
                    params=full_params,
                    timeout=30,
                )
                response.raise_for_status()
                self._last_request_time = time.time()

                return response.json()

            except requests.exceptions.ConnectionError as e:
                last_error = e
                wait = 2 ** attempt  # Backoff exponencial: 2, 4, 8 seg
                logger.warning(
                    f"Error de conexión en intento {attempt}/{self.max_retries}. "
                    f"Reintentando en {wait}s..."
                )
                time.sleep(wait)

            except requests.exceptions.Timeout as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(
                    f"Timeout en intento {attempt}/{self.max_retries}. "
                    f"Reintentando en {wait}s..."
                )
                time.sleep(wait)

            except requests.exceptions.HTTPError as e:
                # No reintentar errores HTTP (4xx, 5xx) excepto 429 y 5xx
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = e
                    wait = 2 ** attempt
                    logger.warning(
                        f"HTTP {response.status_code} en intento {attempt}/{self.max_retries}. "
                        f"Reintentando en {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    raise MoodleAPIError(
                        f"Error HTTP {response.status_code} en {wsfunction}: {response.text[:200]}",
                        wsfunction=wsfunction,
                        errorcode=f"http_{response.status_code}",
                    ) from e

        # Agotados los reintentos
        raise MoodleAPIError(
            f"Fallaron {self.max_retries} intentos de llamar a {wsfunction}: {str(last_error)}",
            wsfunction=wsfunction,
            errorcode="max_retries_exceeded",
        )

    def _rate_limit(self):
        """Aplica el delay configurado entre requests para no saturar el servidor"""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            remaining = self.request_delay - elapsed
            if remaining > 0:
                logger.debug(f"Rate limit: esperando {remaining:.1f}s...")
                time.sleep(remaining)

    # ============================================================
    # Context manager
    # ============================================================

    def close(self):
        """Cierra las sesiones HTTP"""
        self._session.close()
        self._auth.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
