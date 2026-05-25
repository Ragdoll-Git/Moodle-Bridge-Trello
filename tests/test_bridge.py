"""
MoodleAPI-Bridge — Test Integrado.

Test unificado que cubre autenticación, listado de cursos y contenidos
usando mocks de las respuestas HTTP de Moodle. Incluye logging verboso
en tests/logs/.

Ejecutar: pytest tests/ -v --tb=long
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Agregar raíz del proyecto al path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.moodle.auth import MoodleAuth, MoodleAuthError
from src.moodle.client import MoodleClient, MoodleAPIError
from src.moodle.models import (
    Course,
    CourseSection,
    CourseModule,
    ModuleContent,
    SiteInfo,
    MoodleToken,
    BridgeStatus,
    AuthResponse,
    CoursesResponse,
)
from src.services.bridge import BridgeService

# ============================================================
# Logging setup — verboso, escrito a tests/logs/
# ============================================================

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

log_filename = datetime.now().strftime("test_%Y%m%d_%H%M%S.log")
log_path = LOGS_DIR / log_filename

# Configurar logging para archivo y consola
file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s")
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter("%(levelname)-7s │ %(message)s")
)

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console_handler],
)

logger = logging.getLogger("test-bridge")
logger.info(f"Log file: {log_path}")


# ============================================================
# Mock data — Respuestas simuladas de Moodle
# ============================================================

MOCK_BASE_URL = "https://moodle.example.edu/itu"

MOCK_TOKEN_RESPONSE = {
    "token": "abc123def456mock_token_for_testing",
    "privatetoken": "private_mock_789",
}

MOCK_SITE_INFO = {
    "sitename": "Test Moodle Site",
    "username": "12345678",
    "firstname": "Test",
    "lastname": "Test",
    "fullname": "Test User",
    "userid": 42,
    "siteurl": MOCK_BASE_URL,
    "userpictureurl": "https://moodle.example.edu/itu/pluginfile.php/42/user/icon/f1",
    "lang": "es",
    "release": "4.1.2 (Build: 20230512)",
    "version": "2023051200",
}

MOCK_COURSES = [
    {
        "id": 101,
        "shortname": "MAT1-2025",
        "fullname": "Matemática I - Comisión A",
        "displayname": "Matemática I - Comisión A",
        "enrolledusercount": 35,
        "visible": 1,
        "summary": "<p>Curso de Matemática I</p>",
        "format": "topics",
        "startdate": 1709251200,
        "enddate": 1719792000,
        "progress": 45.0,
    },
    {
        "id": 102,
        "shortname": "PROG1-2025",
        "fullname": "Programación I",
        "displayname": "Programación I",
        "enrolledusercount": 40,
        "visible": 1,
        "summary": "<p>Introducción a la programación</p>",
        "format": "topics",
        "startdate": 1709251200,
        "enddate": 1719792000,
        "progress": 60.0,
    },
    {
        "id": 103,
        "shortname": "FIS1-2025",
        "fullname": "Física I",
        "displayname": "Física I",
        "enrolledusercount": 38,
        "visible": 1,
        "summary": "",
        "format": "topics",
        "startdate": 1709251200,
        "enddate": 1719792000,
        "progress": 30.0,
    },
]

MOCK_COURSE_CONTENTS = [
    {
        "id": 1,
        "name": "General",
        "visible": 1,
        "summary": "",
        "section": 0,
        "modules": [
            {
                "id": 201,
                "name": "Programa de la materia",
                "modname": "resource",
                "visible": 1,
                "uservisible": True,
                "contents": [
                    {
                        "type": "file",
                        "filename": "Programa_Mat1_2025.pdf",
                        "filepath": "/",
                        "filesize": 245760,
                        "fileurl": f"{MOCK_BASE_URL}/webservice/pluginfile.php/201/mod_resource/content/0/Programa_Mat1_2025.pdf",
                        "timecreated": 1709251200,
                        "timemodified": 1709251200,
                        "mimetype": "application/pdf",
                    }
                ],
            }
        ],
    },
    {
        "id": 2,
        "name": "Tema 1 - Funciones",
        "visible": 1,
        "summary": "<p>Funciones reales de variable real</p>",
        "section": 1,
        "modules": [
            {
                "id": 202,
                "name": "Apunte teórico - Funciones",
                "modname": "resource",
                "visible": 1,
                "uservisible": True,
                "contents": [
                    {
                        "type": "file",
                        "filename": "Tema1_Funciones_Teoria.pdf",
                        "filepath": "/",
                        "filesize": 512000,
                        "fileurl": f"{MOCK_BASE_URL}/webservice/pluginfile.php/202/mod_resource/content/0/Tema1_Funciones_Teoria.pdf",
                        "timecreated": 1709337600,
                        "timemodified": 1709337600,
                        "mimetype": "application/pdf",
                    }
                ],
            },
            {
                "id": 203,
                "name": "Guía de ejercicios 1",
                "modname": "resource",
                "visible": 1,
                "uservisible": True,
                "contents": [
                    {
                        "type": "file",
                        "filename": "Guia_Ejercicios_1.pdf",
                        "filepath": "/",
                        "filesize": 180224,
                        "fileurl": f"{MOCK_BASE_URL}/webservice/pluginfile.php/203/mod_resource/content/0/Guia_Ejercicios_1.pdf",
                        "timecreated": 1709424000,
                        "timemodified": 1709424000,
                        "mimetype": "application/pdf",
                    }
                ],
            },
            {
                "id": 204,
                "name": "Material complementario",
                "modname": "folder",
                "visible": 1,
                "uservisible": True,
                "contents": [
                    {
                        "type": "file",
                        "filename": "Ejercicios_resueltos.pdf",
                        "filepath": "/",
                        "filesize": 340000,
                        "fileurl": f"{MOCK_BASE_URL}/webservice/pluginfile.php/204/mod_folder/content/0/Ejercicios_resueltos.pdf",
                        "timecreated": 1709510400,
                        "timemodified": 1709510400,
                        "mimetype": "application/pdf",
                    },
                    {
                        "type": "file",
                        "filename": "Formulario.xlsx",
                        "filepath": "/",
                        "filesize": 25600,
                        "fileurl": f"{MOCK_BASE_URL}/webservice/pluginfile.php/204/mod_folder/content/0/Formulario.xlsx",
                        "timecreated": 1709510400,
                        "timemodified": 1709510400,
                        "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    },
                ],
            },
            {
                "id": 205,
                "name": "Videos recomendados",
                "modname": "url",
                "visible": 1,
                "uservisible": True,
                "url": "https://www.youtube.com/watch?v=example",
                "contents": None,
            },
        ],
    },
]


# ============================================================
# Helpers
# ============================================================

def make_mock_response(json_data, status_code=200):
    """Crea un mock de requests.Response"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.text = json.dumps(json_data)
    mock_resp.raise_for_status.return_value = None
    if status_code >= 400:
        from requests.exceptions import HTTPError
        mock_resp.raise_for_status.side_effect = HTTPError(response=mock_resp)
    return mock_resp


# ============================================================
# Tests
# ============================================================

class TestMoodleBridgeIntegrated:
    """
    Test integrado que simula el flujo completo:
    1. Autenticación con Moodle
    2. Obtención de info del sitio
    3. Listado de cursos
    4. Obtención de contenidos de un curso
    5. Verificación de modelos de datos
    6. Verificación del servicio bridge
    """

    # --- Modelos de datos ---

    def test_models_course_safe_name(self):
        """Verifica que los nombres de curso se sanitizan para Windows"""
        logger.info("TEST: Sanitización de nombres de curso")

        course = Course(
            id=1,
            fullname='Matemática I: Análisis <Real> "2025"',
            shortname="MAT1",
        )
        safe = course.safe_name
        logger.info(f"  Original: {course.fullname}")
        logger.info(f"  Sanitizado: {safe}")

        # No debe contener caracteres prohibidos en Windows
        for char in '<>:"/\\|?*':
            assert char not in safe, f"Carácter '{char}' encontrado en nombre sanitizado"

        logger.info("  ✓ Nombre sanitizado correctamente")

    def test_models_module_file_detection(self):
        """Verifica la detección de archivos descargables en módulos"""
        logger.info("TEST: Detección de archivos en módulos")

        # Módulo con archivos
        module_with_files = CourseModule(
            id=1,
            name="Apunte",
            modname="resource",
            contents=[
                ModuleContent(type="file", filename="test.pdf", fileurl="http://x/test.pdf", filesize=1024),
                ModuleContent(type="file", filename="test2.pdf", fileurl="http://x/test2.pdf", filesize=2048),
            ],
        )
        assert module_with_files.has_downloadable_files is True
        assert module_with_files.file_count == 2
        assert module_with_files.total_size == 3072
        logger.info(f"  Módulo con archivos: {module_with_files.file_count} archivos, {module_with_files.total_size} bytes")

        # Módulo sin archivos
        module_no_files = CourseModule(id=2, name="Enlace", modname="url")
        assert module_no_files.has_downloadable_files is False
        assert module_no_files.file_count == 0
        logger.info(f"  Módulo sin archivos: OK")

        logger.info("  ✓ Detección de archivos correcta")

    def test_models_section_safe_name(self):
        """Verifica sanitización de nombres de sección"""
        logger.info("TEST: Sanitización de nombres de sección")

        section = CourseSection(id=1, name="Tema 1: Intro", section=1)
        safe = section.safe_name
        assert ":" not in safe
        logger.info(f"  '{section.name}' → '{safe}'")

        # Sección sin nombre
        section_empty = CourseSection(id=5, name="", section=3)
        safe_empty = section_empty.safe_name
        assert safe_empty.startswith("Seccion_")
        logger.info(f"  Sección vacía → '{safe_empty}'")

        logger.info("  ✓ OK")

    # --- Autenticación ---

    @patch("src.moodle.auth.requests.Session")
    def test_auth_success(self, mock_session_class):
        """Flujo completo de autenticación exitosa"""
        logger.info("TEST: Autenticación exitosa")

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock token request
        mock_session.post.return_value = make_mock_response(MOCK_TOKEN_RESPONSE)
        # Mock site info request
        mock_session.get.return_value = make_mock_response(MOCK_SITE_INFO)

        auth = MoodleAuth(MOCK_BASE_URL)
        token, site_info = auth.authenticate("12345678", "test_password")

        assert token == MOCK_TOKEN_RESPONSE["token"]
        assert site_info.userid == 42
        assert site_info.fullname == "Test User"
        assert site_info.sitename == "Test Moodle Site"
        assert auth.is_authenticated is True

        logger.info(f"  Token: {token[:20]}...")
        logger.info(f"  Usuario: {site_info.fullname} (ID: {site_info.userid})")
        logger.info(f"  Sitio: {site_info.sitename}")
        logger.info("  ✓ Autenticación exitosa")

        auth.close()

    @patch("src.moodle.auth.requests.Session")
    def test_auth_invalid_credentials(self, mock_session_class):
        """Autenticación con credenciales inválidas"""
        logger.info("TEST: Autenticación con credenciales inválidas")

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        error_response = {
            "error": "Invalid login, please try again",
            "errorcode": "invalidlogin",
            "stacktrace": None,
            "debuginfo": None,
            "reproductionlink": None,
        }
        mock_session.post.return_value = make_mock_response(error_response)

        auth = MoodleAuth(MOCK_BASE_URL)
        with pytest.raises(MoodleAuthError) as exc_info:
            auth.authenticate("wrong_user", "wrong_pass")

        assert exc_info.value.errorcode == "invalidlogin"
        logger.info(f"  Error capturado: {exc_info.value}")
        logger.info("  ✓ Error de credenciales manejado correctamente")

        auth.close()

    @patch("src.moodle.auth.requests.Session")
    def test_auth_ws_disabled(self, mock_session_class):
        """Autenticación cuando Web Services está deshabilitado"""
        logger.info("TEST: Web Services deshabilitado")

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        error_response = {
            "error": "Web service moodle_mobile_app is not enabled",
            "errorcode": "enablewsdescription",
        }
        mock_session.post.return_value = make_mock_response(error_response)

        auth = MoodleAuth(MOCK_BASE_URL)
        with pytest.raises(MoodleAuthError) as exc_info:
            auth.authenticate("12345678", "test_password")

        assert exc_info.value.errorcode == "ws_disabled"
        logger.info(f"  Error capturado: {exc_info.value}")
        logger.info("  ✓ Error de WS deshabilitado manejado correctamente")

        auth.close()

    # --- Cliente API ---

    @patch("src.moodle.client.requests.Session")
    @patch.object(MoodleAuth, "authenticate")
    def test_client_get_courses(self, mock_auth_authenticate, mock_client_session_class):
        """Obtención de lista de cursos"""
        logger.info("TEST: Obtención de cursos")

        # Mock auth.authenticate para devolver token + SiteInfo directamente
        mock_site_info = SiteInfo(**MOCK_SITE_INFO)
        mock_auth_authenticate.return_value = (MOCK_TOKEN_RESPONSE["token"], mock_site_info)

        # Mock session para llamadas del client
        mock_client_session = MagicMock()
        mock_client_session_class.return_value = mock_client_session
        mock_client_session.get.return_value = make_mock_response(MOCK_COURSES)

        client = MoodleClient(MOCK_BASE_URL, request_delay=0)  # Sin delay para tests
        client.authenticate("12345678", "test_password")
        courses = client.get_user_courses()

        assert len(courses) == 3
        assert courses[0].id == 101
        assert courses[0].fullname == "Matemática I - Comisión A"
        assert courses[1].fullname == "Programación I"
        assert courses[2].fullname == "Física I"

        for c in courses:
            logger.info(f"  [{c.id}] {c.fullname} (progreso: {c.progress}%)")

        logger.info(f"  Total: {len(courses)} cursos")
        logger.info("  ✓ Cursos obtenidos correctamente")

        client.close()

    @patch("src.moodle.client.requests.Session")
    @patch.object(MoodleAuth, "authenticate")
    def test_client_get_course_contents(self, mock_auth_authenticate, mock_client_session_class):
        """Obtención de contenidos de un curso"""
        logger.info("TEST: Obtención de contenidos del curso")

        # Mock auth
        mock_site_info = SiteInfo(**MOCK_SITE_INFO)
        mock_auth_authenticate.return_value = (MOCK_TOKEN_RESPONSE["token"], mock_site_info)

        # Mock session
        mock_client_session = MagicMock()
        mock_client_session_class.return_value = mock_client_session
        mock_client_session.get.return_value = make_mock_response(MOCK_COURSE_CONTENTS)

        client = MoodleClient(MOCK_BASE_URL, request_delay=0)
        client.authenticate("12345678", "test_password")
        sections = client.get_course_contents(101)

        assert len(sections) == 2
        assert sections[0].name == "General"
        assert sections[1].name == "Tema 1 - Funciones"

        # Verificar módulos del Tema 1
        tema1_modules = sections[1].modules
        assert len(tema1_modules) == 4  # resource, resource, folder, url

        # Contar archivos descargables: 1 programa + 1 teoría + 1 guía + 2 en carpeta = 5
        total_files = sum(m.file_count for s in sections for m in s.modules)
        assert total_files == 5

        for s in sections:
            logger.info(f"  Sección: {s.name}")
            for m in s.modules:
                logger.info(f"    [{m.modname}] {m.name} ({m.file_count} archivos)")

        logger.info(f"  Total archivos descargables: {total_files}")
        logger.info("  ✓ Contenidos obtenidos correctamente")

        client.close()

    @patch("src.moodle.client.requests.Session")
    @patch("src.moodle.auth.requests.Session")
    def test_client_not_authenticated(self, mock_auth_session_class, mock_client_session_class):
        """Verificar error al consultar sin autenticar"""
        logger.info("TEST: Consulta sin autenticación")

        client = MoodleClient(MOCK_BASE_URL, request_delay=0)

        with pytest.raises(MoodleAPIError):
            client.get_user_courses()

        logger.info("  ✓ Error de no autenticado capturado correctamente")

        client.close()

    # --- Bridge Service ---

    @patch("src.services.bridge.MoodleClient")
    def test_bridge_service_status(self, mock_client_class):
        """Estado del bridge service"""
        logger.info("TEST: Estado del bridge service")

        service = BridgeService()
        status = service.get_status()

        assert status.service == "MoodleAPI-Bridge"
        assert status.status == "running"
        assert status.version == "0.1.0"
        assert status.moodle_connected is False
        assert status.uptime_seconds is not None

        logger.info(f"  Service: {status.service}")
        logger.info(f"  Status: {status.status}")
        logger.info(f"  Version: {status.version}")
        logger.info(f"  Uptime: {status.uptime_seconds}s")
        logger.info("  ✓ Estado correcto")

    @patch("src.services.bridge.settings")
    def test_bridge_auth_no_credentials(self, mock_settings):
        """Bridge auth sin credenciales configuradas"""
        logger.info("TEST: Bridge auth sin credenciales")

        # Asegurar que settings no tiene credenciales de fallback
        mock_settings.moodle_username = ""
        mock_settings.moodle_password = ""
        mock_settings.moodle_base_url = MOCK_BASE_URL
        mock_settings.is_moodle_configured = False

        service = BridgeService()
        # Pasar strings vacíos — y settings tampoco tiene nada
        result = service.moodle_authenticate("", "")

        assert result.success is False
        assert "no configuradas" in (result.message.lower() + " " + (result.error or "").lower())

        logger.info(f"  Resultado: success={result.success}, message='{result.message}'")
        logger.info(f"  Error: {result.error}")
        logger.info("  ✓ Error manejado correctamente")

    @patch("src.services.bridge.MoodleClient")
    def test_bridge_courses_not_authenticated(self, mock_client_class):
        """Bridge cursos sin autenticar"""
        logger.info("TEST: Bridge cursos sin autenticar")

        service = BridgeService()
        result = service.moodle_get_courses()

        assert result.success is False
        assert "no autenticado" in result.message.lower() or "no autenticado" in (result.error or "").lower()

        logger.info(f"  Resultado: {result.message}")
        logger.info("  ✓ Error manejado correctamente")

    # --- Response Models ---

    def test_bridge_status_model(self):
        """Verificar modelo BridgeStatus"""
        logger.info("TEST: Modelo BridgeStatus")

        status = BridgeStatus(
            moodle_configured=True,
            moodle_connected=True,
            uptime_seconds=123.4,
        )

        assert status.service == "MoodleAPI-Bridge"
        assert status.moodle_configured is True
        assert status.moodle_connected is True
        assert status.uptime_seconds == 123.4

        logger.info(f"  {status.model_dump_json(indent=2)}")
        logger.info("  ✓ Modelo correcto")

    def test_courses_response_model(self):
        """Verificar modelo CoursesResponse"""
        logger.info("TEST: Modelo CoursesResponse")

        courses = [Course(**c) for c in MOCK_COURSES]
        response = CoursesResponse(
            success=True,
            message=f"Se encontraron {len(courses)} cursos",
            total_courses=len(courses),
            courses=courses,
        )

        assert response.success is True
        assert response.total_courses == 3
        assert len(response.courses) == 3

        logger.info(f"  Total: {response.total_courses} cursos")
        logger.info("  ✓ Modelo correcto")


# ============================================================
# Ejecución directa
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=long", "-s"])
