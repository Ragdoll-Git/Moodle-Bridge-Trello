"""
MoodleAPI-Bridge — Servicio Bridge.

Capa de servicio que gestiona el estado global de las conexiones
a Moodle y servicios externos (Trello). Actúa como punto
central de coordinación entre las rutas API y los clientes.
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

from ..config import settings
from ..moodle.client import MoodleClient, MoodleAPIError
from ..moodle.auth import MoodleAuthError
from ..moodle.models import (
    SiteInfo,
    Course,
    CourseSection,
    Assignment,
    CourseAssignments,
    Activity,
    BridgeStatus,
    AuthResponse,
    CoursesResponse,
    CourseContentsResponse,
    AssignmentsResponse,
)
from ..trello.client import TrelloClient, TrelloAPIError
from ..trello.models import (
    TrelloBoard,
    TrelloList,
    TrelloCard,
    TrelloSyncResult,
    SyncedCard,
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
        self._trello_client: Optional[TrelloClient] = None
        self._trello_connected: Optional[bool] = None
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
            trello_connected=self._trello_connected is True,
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
    # Moodle — Autenticación
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

    # ============================================================
    # Moodle — Cursos
    # ============================================================

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
    # Moodle — Assignments y Actividades
    # ============================================================

    def moodle_get_assignments(
        self,
        course_ids: list[int] | None = None,
    ) -> AssignmentsResponse:
        """
        Obtiene las tareas de Moodle. Si no se especifican course_ids,
        obtiene las de todos los cursos del usuario.

        Combina:
        1. mod_assign_get_assignments para datos de entrega (fechas)
        2. core_course_get_contents para detectar actividades ocultas
           y foros con deadlines

        Args:
            course_ids: IDs de cursos específicos (None = todos)

        Returns:
            AssignmentsResponse con assignments y activities
        """
        if not self._moodle_client or not self._moodle_client.is_authenticated:
            return AssignmentsResponse(
                success=False,
                message="No autenticado",
                error="Primero autenticate con POST /api/moodle/auth",
            )

        try:
            # Si no se especificaron cursos, obtener todos
            if not course_ids:
                courses = self._moodle_client.get_user_courses()
                course_ids = [c.id for c in courses]
                course_map = {c.id: c.fullname for c in courses}
            else:
                # Intentar obtener nombres
                try:
                    courses = self._moodle_client.get_user_courses()
                    course_map = {c.id: c.fullname for c in courses}
                except Exception:
                    course_map = {}

            # 1. Obtener assignments via mod_assign_get_assignments
            course_assignments = self._moodle_client.get_assignments(course_ids)

            # 2. Obtener actividades (assign + forum) de cada curso
            all_activities: list[Activity] = []
            for cid in course_ids:
                try:
                    activities = self._moodle_client.get_course_activities(
                        course_id=cid,
                        course_name=course_map.get(cid, ""),
                        modnames=["assign", "forum"],
                    )
                    all_activities.extend(activities)
                except Exception as e:
                    logger.warning(f"Error al obtener actividades del curso {cid}: {e}")

            # Enriquecer activities con datos de assignment (fechas)
            # Crear lookup: instance_id → Assignment
            assign_lookup: dict[int, Assignment] = {}
            for ca in course_assignments:
                for a in ca.assignments:
                    assign_lookup[a.id] = a

            for activity in all_activities:
                if activity.modname == "assign" and activity.instance:
                    assign = assign_lookup.get(activity.instance)
                    if assign:
                        activity.duedate = assign.duedate
                        activity.cutoffdate = assign.cutoffdate

            total = sum(len(ca.assignments) for ca in course_assignments)

            return AssignmentsResponse(
                success=True,
                message=(
                    f"Se encontraron {total} assignments y "
                    f"{len(all_activities)} actividades (assign+forum) "
                    f"en {len(course_ids)} cursos"
                ),
                total_assignments=total,
                courses=course_assignments,
                activities=all_activities,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error al obtener assignments: {error_msg}")
            self._log_error("moodle_assignments", error_msg)
            return AssignmentsResponse(
                success=False,
                message="Error al obtener assignments",
                error=error_msg,
            )

    # ============================================================
    # Trello — Operaciones
    # ============================================================

    def _get_trello_client(self) -> TrelloClient:
        """Obtiene o crea el cliente de Trello"""
        if not settings.is_trello_configured:
            raise TrelloAPIError(
                "Trello no configurado. Agregá TRELLO_API_KEY y TRELLO_TOKEN en .env"
            )

        if self._trello_client is None:
            self._trello_client = TrelloClient(
                api_key=settings.trello_api_key,
                token=settings.trello_token,
                request_delay=settings.trello_request_delay,
            )

        return self._trello_client

    def trello_get_boards(self) -> dict:
        """Lista los boards de Trello del usuario"""
        try:
            client = self._get_trello_client()
            boards = client.get_boards()
            return {
                "success": True,
                "message": f"Se encontraron {len(boards)} boards",
                "boards": [b.model_dump() for b in boards],
            }
        except TrelloAPIError as e:
            return {"success": False, "message": str(e), "boards": []}
        except Exception as e:
            self._log_error("trello_boards", str(e))
            return {"success": False, "message": f"Error: {e}", "boards": []}

    def trello_get_status(self) -> dict:
        """Estado real de la conexión con Trello"""
        if not settings.is_trello_configured:
            self._trello_connected = False
            return {
                "success": False,
                "configured": False,
                "connected": False,
                "message": "Trello no configurado. Agregá TRELLO_API_KEY y TRELLO_TOKEN en .env",
            }

        try:
            client = self._get_trello_client()
            boards = client.get_boards()
            self._trello_connected = True
            return {
                "success": True,
                "configured": True,
                "connected": True,
                "message": f"Conectado a Trello ({len(boards)} boards disponibles)",
                "boards_count": len(boards),
            }
        except TrelloAPIError as e:
            self._trello_connected = False
            return {
                "success": False,
                "configured": True,
                "connected": False,
                "message": f"Error de conexión: {e}",
            }

    def trello_sync_assignments(
        self,
        board_name: Optional[str] = None,
        course_ids: list[int] | None = None,
    ) -> TrelloSyncResult:
        """
        Sincroniza tareas de Moodle a Trello.

        Flujo:
        1. Obtener assignments de Moodle
        2. Buscar/usar board "Facu" (o el especificado)
        3. Crear una lista por curso
        4. Por cada assignment: crear tarjeta o actualizar si ya existe

        Args:
            board_name: Nombre del board (default: settings.trello_default_board_name)
            course_ids: IDs de cursos específicos (None = todos)

        Returns:
            TrelloSyncResult con el detalle de la operación
        """
        # Verificar autenticación Moodle
        if not self._moodle_client or not self._moodle_client.is_authenticated:
            return TrelloSyncResult(
                success=False,
                message="No autenticado en Moodle",
                error="Primero autenticate con POST /api/moodle/auth",
            )

        try:
            trello = self._get_trello_client()
        except TrelloAPIError as e:
            return TrelloSyncResult(
                success=False,
                message="Error de Trello",
                error=str(e),
            )

        try:
            # 1. Obtener assignments de Moodle
            logger.info("=== Iniciando sincronización Moodle → Trello ===")

            assignments_resp = self.moodle_get_assignments(course_ids)
            if not assignments_resp.success:
                return TrelloSyncResult(
                    success=False,
                    message="Error al obtener assignments de Moodle",
                    error=assignments_resp.error,
                )

            # 2. Buscar board
            target_board_name = board_name or settings.trello_default_board_name
            logger.info(f"Buscando board '{target_board_name}'...")

            board = trello.find_board_by_name(target_board_name)
            if not board:
                return TrelloSyncResult(
                    success=False,
                    message=f"No se encontró el board '{target_board_name}' en Trello",
                    error=(
                        f"Creá un board llamado '{target_board_name}' en Trello o "
                        f"cambiá TRELLO_DEFAULT_BOARD_NAME en .env"
                    ),
                )

            logger.info(f"Board encontrado: '{board.name}' (id: {board.id})")

            # 3. Cachear tarjetas existentes para detección de duplicados
            existing_cards = trello.get_board_cards(board.id)
            logger.info(f"Tarjetas existentes en board: {len(existing_cards)}")

            # 4. Crear una lista por curso y sincronizar tarjetas
            synced_cards: list[SyncedCard] = []
            created = 0
            updated = 0
            skipped = 0

            for course_assign in assignments_resp.courses:
                if not course_assign.assignments:
                    continue

                # Limpiar nombre del curso para la lista
                list_name = self._clean_course_name(course_assign.fullname)
                logger.info(f"Procesando curso: '{list_name}' ({len(course_assign.assignments)} assignments)")

                # Buscar si la lista existe (incluyendo archivadas/cerradas)
                existing_list = trello.find_list_by_name(board.id, list_name)

                # Si la lista existe y está cerrada/archivada, omitimos el curso completo
                if existing_list and existing_list.closed:
                    logger.info(f"  - Omitido curso completo: '{list_name}' (la lista está archivada en Trello)")
                    for assign in course_assign.assignments:
                        card_name = assign.name
                        due_str = self._timestamp_to_iso(assign.duedate) if assign.duedate else None
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=course_assign.fullname,
                            card_id="",
                            card_url="",
                            action="skipped",
                            due_date=due_str,
                            due_complete=False,
                        ))
                        skipped += 1
                    continue

                # Obtener o usar lista existente (lazy loading)
                trello_list = existing_list if (existing_list and not existing_list.closed) else None

                for assign in course_assign.assignments:
                    card_name = assign.name
                    card_desc = self._build_card_description(assign, course_assign.fullname)
                    due_str = self._timestamp_to_iso(assign.duedate) if assign.duedate else None

                    # Buscar tarjeta existente (incluyendo archivadas)
                    existing = trello.find_card_by_name(
                        board.id, card_name, cards_cache=existing_cards
                    )

                    # Si ya existe y está completada (dueComplete) o archivada (closed) en Trello, omitir
                    if existing and (existing.closed or existing.dueComplete):
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=course_assign.fullname,
                            card_id=existing.id,
                            card_url=existing.url,
                            action="skipped",
                            due_date=due_str,
                            due_complete=existing.dueComplete,
                        ))
                        skipped += 1
                        logger.info(f"  - Omitida: '{card_name}' (ya está completada/archivada en Trello)")
                        continue

                    # Verificar estado de entrega en Moodle
                    is_completed = self._is_assignment_submitted(assign.id)

                    # Si la tarjeta NO existe y ya está entregada en Moodle, omitir su creación
                    if not existing and is_completed:
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=course_assign.fullname,
                            card_id="",
                            card_url="",
                            action="skipped",
                            due_date=due_str,
                            due_complete=True,
                        ))
                        skipped += 1
                        logger.info(f"  - Omitida creación: '{card_name}' (ya entregada en Moodle)")
                        continue

                    if existing:
                        # Actualizar tarjeta existente sin pasar idList para no moverla de su lista
                        trello.update_card(
                            card_id=existing.id,
                            desc=card_desc,
                            due=due_str,
                            dueComplete=is_completed,
                        )
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=course_assign.fullname,
                            card_id=existing.id,
                            card_url=existing.url,
                            action="updated",
                            due_date=due_str,
                            due_complete=is_completed,
                        ))
                        updated += 1
                        logger.info(f"  ↻ Actualizada: '{card_name}' (completada: {is_completed})")
                    else:
                        # Crear nueva tarjeta (si no tenemos trello_list aún, la obtenemos/creamos)
                        if trello_list is None:
                            trello_list = trello.get_or_create_list(board.id, list_name)

                        new_card = trello.create_card(
                            list_id=trello_list.id,
                            name=card_name,
                            desc=card_desc,
                            due=due_str,
                            dueComplete=is_completed,
                        )
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=course_assign.fullname,
                            card_id=new_card.id,
                            card_url=new_card.url,
                            action="created",
                            due_date=due_str,
                            due_complete=is_completed,
                        ))
                        created += 1
                        logger.info(f"  ✓ Creada: '{card_name}' (completada: {is_completed})")

            # También sincronizar foros con deadline desde activities
            for activity in assignments_resp.activities:
                if activity.modname == "forum":
                    list_name = self._clean_course_name(activity.course_name)
                    if not list_name:
                        continue

                    card_name = f"[Foro] {activity.name}"
                    card_desc = self._build_activity_description(activity)

                    # Buscar si la lista existe
                    existing_list = trello.find_list_by_name(board.id, list_name)
                    if existing_list and existing_list.closed:
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=activity.course_name,
                            card_id="",
                            card_url="",
                            action="skipped",
                            due_complete=False,
                        ))
                        skipped += 1
                        logger.info(f"  - Omitido foro: '{card_name}' (la lista '{list_name}' está archivada en Trello)")
                        continue

                    # Buscar tarjeta existente (incluyendo archivadas)
                    existing = trello.find_card_by_name(
                        board.id, card_name, cards_cache=existing_cards
                    )

                    # Si ya existe y está completada (dueComplete) o archivada (closed) en Trello, omitir
                    if existing and (existing.closed or existing.dueComplete):
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=activity.course_name,
                            card_id=existing.id,
                            card_url=existing.url,
                            action="skipped",
                            due_complete=existing.dueComplete,
                        ))
                        skipped += 1
                        logger.info(f"  - Omitido: '{card_name}' (foro ya completado/archivado en Trello)")
                        continue

                    if existing:
                        trello.update_card(
                            card_id=existing.id,
                            desc=card_desc,
                        )
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=activity.course_name,
                            card_id=existing.id,
                            card_url=existing.url,
                            action="updated",
                        ))
                        updated += 1
                        logger.info(f"  ↻ Actualizado foro: '{card_name}'")
                    else:
                        trello_list = existing_list if (existing_list and not existing_list.closed) else None
                        if trello_list is None:
                            trello_list = trello.get_or_create_list(board.id, list_name)

                        new_card = trello.create_card(
                            list_id=trello_list.id,
                            name=card_name,
                            desc=card_desc,
                        )
                        synced_cards.append(SyncedCard(
                            assignment_name=card_name,
                            course_name=activity.course_name,
                            card_id=new_card.id,
                            card_url=new_card.url,
                            action="created",
                        ))
                        created += 1
                        logger.info(f"  ✓ Creado foro: '{card_name}' en lista '{list_name}'")

            total_synced = created + updated
            logger.info(
                f"=== Sincronización completada: "
                f"{created} creadas, {updated} actualizadas, {skipped} omitidas ==="
            )

            return TrelloSyncResult(
                success=True,
                message=(
                    f"Sincronización completada: {created} creadas, "
                    f"{updated} actualizadas"
                ),
                board_id=board.id,
                board_name=board.name,
                board_url=board.url,
                total_synced=total_synced,
                created=created,
                updated=updated,
                skipped=skipped,
                cards=synced_cards,
            )

        except TrelloAPIError as e:
            error_msg = f"Error de Trello: {e}"
            logger.error(error_msg)
            self._log_error("trello_sync", error_msg)
            return TrelloSyncResult(
                success=False,
                message="Error durante la sincronización",
                error=error_msg,
            )
        except Exception as e:
            error_msg = f"Error inesperado: {e}"
            logger.error(error_msg, exc_info=True)
            self._log_error("trello_sync", error_msg)
            return TrelloSyncResult(
                success=False,
                message="Error inesperado durante la sincronización",
                error=error_msg,
            )

    # ============================================================
    # Helpers
    # ============================================================

    def _is_assignment_submitted(self, assign_id: int) -> bool:
        """Verifica si la tarea está entregada en Moodle"""
        if not self._moodle_client or not self._moodle_client.is_authenticated:
            return False
        try:
            status_data = self._moodle_client.get_assignment_submission_status(assign_id)
            # En Moodle, el estado de la entrega está en lastattempt -> submission -> status
            last_attempt = status_data.get("lastattempt", {})
            if last_attempt:
                submission = last_attempt.get("submission", {})
                if submission:
                    status = submission.get("status", "")
                    if status == "submitted":
                        return True
            return False
        except Exception as e:
            logger.warning(f"Error al obtener estado de entrega para assignment {assign_id}: {e}")
            return False

    @staticmethod
    def _clean_course_name(fullname: str) -> str:

        """
        Limpia el nombre de un curso para usarlo como nombre de lista.
        Ejemplo: "COM101 - Programación I (2026)" → "Programación I"
        """
        if not fullname:
            return fullname

        name = fullname.strip()

        # Remover prefijos tipo código (ej: "COM101 - ", "MAT200-")
        name = re.sub(r'^[A-Z]{2,5}\d{2,4}\s*[-–]\s*', '', name)

        # Remover sufijos entre paréntesis (ej: "(2026)", "(Comisión A)")
        name = re.sub(r'\s*\(.*?\)\s*$', '', name)

        return name.strip() or fullname.strip()

    @staticmethod
    def _timestamp_to_iso(ts: int | None) -> str | None:
        """Convierte timestamp Unix a ISO 8601 para Trello"""
        if not ts or ts <= 0:
            return None
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    @staticmethod
    def _build_card_description(assign: Assignment, course_name: str) -> str:
        """Construye la descripción Markdown de una tarjeta para un assignment"""
        lines = [f"**Curso:** {course_name}", ""]

        if assign.intro:
            # Limpiar HTML básico del intro
            clean_intro = re.sub(r'<[^>]+>', '', assign.intro).strip()
            if clean_intro:
                lines.append(f"**Descripción:**\n{clean_intro}")
                lines.append("")

        if assign.duedate and assign.duedate > 0:
            dt = datetime.fromtimestamp(assign.duedate)
            lines.append(f"📅 **Fecha de entrega:** {dt.strftime('%d/%m/%Y %H:%M')}")

        if assign.cutoffdate and assign.cutoffdate > 0:
            dt = datetime.fromtimestamp(assign.cutoffdate)
            lines.append(f"⏰ **Fecha límite:** {dt.strftime('%d/%m/%Y %H:%M')}")

        if assign.allowsubmissionsfromdate and assign.allowsubmissionsfromdate > 0:
            dt = datetime.fromtimestamp(assign.allowsubmissionsfromdate)
            lines.append(f"📂 **Abierto desde:** {dt.strftime('%d/%m/%Y %H:%M')}")

        if assign.cmid and assign.cmid > 0:
            moodle_url = f"{settings.moodle_base_url}/mod/assign/view.php?id={assign.cmid}"
            lines.append(f"🔗 [Abrir en Moodle]({moodle_url})")

        lines.append("")
        lines.append("---")
        lines.append(f"*Sincronizado desde Moodle (ID: {assign.id}, CMID: {assign.cmid})*")

        return "\n".join(lines)

    @staticmethod
    def _build_activity_description(activity: Activity) -> str:
        """Construye descripción para una actividad genérica (foro, etc.)"""
        lines = [f"**Curso:** {activity.course_name}", ""]

        if activity.section_name:
            lines.append(f"**Sección:** {activity.section_name}")

        if activity.description:
            clean_desc = re.sub(r'<[^>]+>', '', activity.description).strip()
            if clean_desc:
                lines.append(f"\n{clean_desc}")

        if activity.is_hidden:
            lines.append("\n⚠️ *Actividad oculta o con acceso restringido*")

        if activity.url:
            lines.append(f"\n🔗 [Abrir en Moodle]({activity.url})")

        lines.append("")
        lines.append("---")
        lines.append(f"*Sincronizado desde Moodle (módulo: {activity.modname}, ID: {activity.id})*")

        return "\n".join(lines)

    # ============================================================
    # Cleanup
    # ============================================================

    def shutdown(self):
        """Cierra todas las conexiones"""
        if self._moodle_client:
            self._moodle_client.close()
            self._moodle_client = None
        if self._trello_client:
            self._trello_client.close()
            self._trello_client = None
        logger.info("Bridge service shut down")


# Instancia global del servicio
bridge_service = BridgeService()
