"""
MoodleAPI-Bridge — Autenticación con Moodle.

Maneja la obtención del token de acceso mediante las credenciales
del estudiante y la validación del token via core_webservice_get_site_info.
"""

import logging
import requests
from typing import Optional, Tuple

from .models import MoodleToken, SiteInfo, MoodleError

logger = logging.getLogger("moodle-bridge.auth")


class MoodleAuthError(Exception):
    """Error de autenticación con Moodle"""

    def __init__(self, message: str, errorcode: Optional[str] = None):
        self.errorcode = errorcode
        super().__init__(message)


class MoodleAuth:
    """
    Gestiona la autenticación contra la API de Moodle.

    Usa el servicio moodle_mobile_app para obtener un token temporal
    que permite acceder a la API REST como el usuario autenticado.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token_url = f"{self.base_url}/login/token.php"
        self.api_url = f"{self.base_url}/webservice/rest/server.php"
        self._token: Optional[str] = None
        self._site_info: Optional[SiteInfo] = None
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "MoodleAPI-Bridge/0.1.0 (Student Resource Organizer)"
        })

    @property
    def token(self) -> Optional[str]:
        return self._token

    @property
    def site_info(self) -> Optional[SiteInfo]:
        return self._site_info

    @property
    def userid(self) -> Optional[int]:
        return self._site_info.userid if self._site_info else None

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None and self._site_info is not None

    def authenticate(self, username: str, password: str) -> Tuple[str, SiteInfo]:
        """
        Flujo completo de autenticación:
        1. Obtener token via /login/token.php
        2. Validar token y obtener info del usuario via core_webservice_get_site_info

        Returns:
            Tupla (token, site_info)

        Raises:
            MoodleAuthError: Si las credenciales son inválidas o el servicio está deshabilitado
        """
        logger.info("Iniciando autenticación con Moodle...")
        logger.info(f"  URL base: {self.base_url}")
        logger.info(f"  Usuario: {username}")

        # Paso 1: Obtener token
        token = self._get_token(username, password)
        self._token = token
        logger.info("Token obtenido exitosamente")

        # Paso 2: Obtener info del sitio y validar token
        site_info = self._get_site_info(token)
        self._site_info = site_info
        logger.info(f"Autenticado como: {site_info.fullname} (userid: {site_info.userid})")
        logger.info(f"Sitio: {site_info.sitename}")

        return token, site_info

    def _get_token(self, username: str, password: str) -> str:
        """
        Obtiene un token de acceso enviando credenciales al endpoint
        de autenticación del servicio moodle_mobile_app.
        """
        payload = {
            "username": username,
            "password": password,
            "service": "moodle_mobile_app",
        }

        logger.debug(f"POST {self.token_url}")

        try:
            response = self._session.post(self.token_url, data=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise MoodleAuthError(
                f"No se pudo conectar a {self.base_url}. "
                "Verificá tu conexión a internet y que la URL sea correcta.",
                errorcode="connection_error",
            ) from e
        except requests.exceptions.Timeout as e:
            raise MoodleAuthError(
                f"Timeout al conectar con {self.base_url}. "
                "El servidor puede estar caído o lento.",
                errorcode="timeout",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise MoodleAuthError(
                f"Error HTTP {response.status_code} al autenticar. "
                f"Respuesta: {response.text[:200]}",
                errorcode=f"http_{response.status_code}",
            ) from e

        data = response.json()

        # Verificar si Moodle devolvió un error
        if "error" in data:
            error = MoodleError(**data)
            error_msg = error.error or error.message or "Error desconocido"

            if error.errorcode == "invalidlogin":
                raise MoodleAuthError(
                    "Credenciales inválidas. Verificá tu usuario y contraseña.",
                    errorcode="invalidlogin",
                )
            elif error.errorcode == "enablewsdescription":
                raise MoodleAuthError(
                    "Los Web Services están deshabilitados en este Moodle. "
                    "El administrador del sitio necesita habilitar el servicio moodle_mobile_app.",
                    errorcode="ws_disabled",
                )
            else:
                raise MoodleAuthError(
                    f"Error de Moodle: {error_msg} (código: {error.errorcode})",
                    errorcode=error.errorcode,
                )

        if "token" not in data:
            raise MoodleAuthError(
                "La respuesta de Moodle no contiene un token. "
                f"Respuesta: {str(data)[:200]}",
                errorcode="no_token",
            )

        return data["token"]

    def _get_site_info(self, token: str) -> SiteInfo:
        """
        Valida el token obteniendo información del sitio y del usuario
        via core_webservice_get_site_info.
        """
        params = {
            "wstoken": token,
            "wsfunction": "core_webservice_get_site_info",
            "moodlewsrestformat": "json",
        }

        logger.debug(f"GET {self.api_url} [core_webservice_get_site_info]")

        try:
            response = self._session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise MoodleAuthError(
                f"Error al consultar info del sitio: {str(e)}",
                errorcode="site_info_error",
            ) from e

        data = response.json()

        # Verificar errores
        if "exception" in data or "errorcode" in data:
            error = MoodleError(**data)
            raise MoodleAuthError(
                f"Error al obtener info del sitio: {error.message or error.error}",
                errorcode=error.errorcode,
            )

        return SiteInfo(**data)

    def close(self):
        """Cierra la sesión HTTP"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
