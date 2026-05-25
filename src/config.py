"""
MoodleAPI-Bridge — Configuración central.

Carga variables de entorno desde .env y las expone como un objeto Settings
validado por Pydantic. Todas las configuraciones del servicio se centralizan aquí.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

# Ruta raíz del proyecto (un nivel arriba de src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Cargar .env si existe
_env_path = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Configuración del bridge, cargada desde variables de entorno o .env"""

    # --- Moodle ---
    moodle_base_url: str = Field(
        default="https://moodle.example.edu/itu",
        description="URL base del Moodle (sin trailing slash)",
    )
    moodle_username: str = Field(
        default="",
        description="Usuario de Moodle (DNI del alumno)",
    )
    moodle_password: str = Field(
        default="",
        description="Contraseña de Moodle",
    )

    # --- Servicio ---
    bridge_host: str = Field(
        default="0.0.0.0",
        description="Host donde escucha el bridge",
    )
    bridge_port: int = Field(
        default=8000,
        description="Puerto del bridge",
    )

    # --- Rate Limiting ---
    request_delay: float = Field(
        default=1.5,
        description="Segundos de espera entre requests a Moodle",
    )
    max_retries: int = Field(
        default=3,
        description="Máximo de reintentos por request fallido",
    )

    # --- Futuro: Google ---
    google_client_id: str = Field(default="", description="Google OAuth Client ID")
    google_client_secret: str = Field(default="", description="Google OAuth Client Secret")
    google_redirect_uri: str = Field(default="", description="Google OAuth Redirect URI")

    # --- Futuro: Trello ---
    trello_api_key: str = Field(default="", description="Trello API Key")
    trello_token: str = Field(default="", description="Trello Token")

    model_config = {
        "env_file": str(_env_path),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @property
    def moodle_token_url(self) -> str:
        """URL para obtener el token de autenticación"""
        return f"{self.moodle_base_url}/login/token.php"

    @property
    def moodle_api_url(self) -> str:
        """URL del endpoint REST de la API de Moodle"""
        return f"{self.moodle_base_url}/webservice/rest/server.php"

    @property
    def is_moodle_configured(self) -> bool:
        """Verifica si las credenciales de Moodle están configuradas"""
        return bool(self.moodle_username and self.moodle_password)

    @property
    def is_google_configured(self) -> bool:
        """Verifica si las credenciales de Google están configuradas"""
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def is_trello_configured(self) -> bool:
        """Verifica si las credenciales de Trello están configuradas"""
        return bool(self.trello_api_key and self.trello_token)


# Instancia global (singleton)
settings = Settings()
