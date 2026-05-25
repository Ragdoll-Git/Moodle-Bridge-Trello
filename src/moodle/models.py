"""
MoodleAPI-Bridge — Modelos de datos.

Define las estructuras de datos Pydantic para la comunicación con Moodle
y las respuestas de la API del bridge. Todos los modelos usan validación
estricta para detectar cambios en la API de Moodle tempranamente.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# Modelos de autenticación
# ============================================================

class MoodleToken(BaseModel):
    """Respuesta de /login/token.php"""
    token: str
    privatetoken: Optional[str] = None


class MoodleError(BaseModel):
    """Error devuelto por la API de Moodle"""
    error: Optional[str] = None
    errorcode: Optional[str] = None
    message: Optional[str] = None
    exception: Optional[str] = None
    debuginfo: Optional[str] = None


# ============================================================
# Modelos de información del sitio
# ============================================================

class SiteInfo(BaseModel):
    """Respuesta de core_webservice_get_site_info"""
    sitename: str = ""
    username: str = ""
    firstname: str = ""
    lastname: str = ""
    fullname: str = ""
    userid: int = 0
    siteurl: str = ""
    userpictureurl: Optional[str] = None
    lang: str = "es"
    release: Optional[str] = None
    version: Optional[str] = None

    model_config = {"extra": "allow"}


# ============================================================
# Modelos de cursos
# ============================================================

class Course(BaseModel):
    """Curso en el que está matriculado el usuario"""
    id: int
    shortname: str = ""
    fullname: str = ""
    displayname: Optional[str] = None
    enrolledusercount: Optional[int] = None
    idnumber: str = ""
    visible: Optional[int] = 1
    summary: Optional[str] = ""
    summaryformat: Optional[int] = None
    format: Optional[str] = None
    showgrades: Optional[bool] = None
    lang: Optional[str] = ""
    enablecompletion: Optional[bool] = None
    completionhascriteria: Optional[bool] = None
    completionusertracked: Optional[bool] = None
    category: Optional[int] = None
    startdate: Optional[int] = None
    enddate: Optional[int] = None
    lastaccess: Optional[int] = None
    progress: Optional[float] = None

    model_config = {"extra": "allow"}

    @property
    def safe_name(self) -> str:
        """Nombre sanitizado para usar como carpeta en Windows"""
        name = self.displayname or self.fullname or self.shortname
        # Caracteres no permitidos en Windows
        for char in '<>:"/\\|?*':
            name = name.replace(char, "_")
        return name.strip().rstrip(".")


# ============================================================
# Modelos de contenido de cursos
# ============================================================

class ModuleContent(BaseModel):
    """Archivo o recurso dentro de un módulo"""
    type: Optional[str] = None  # "file", "url", etc.
    filename: Optional[str] = None
    filepath: Optional[str] = None
    filesize: Optional[int] = None
    fileurl: Optional[str] = None
    timecreated: Optional[int] = None
    timemodified: Optional[int] = None
    sortorder: Optional[int] = None
    mimetype: Optional[str] = None
    isexternalfile: Optional[bool] = None
    userid: Optional[int] = None
    author: Optional[str] = None
    license: Optional[str] = None

    model_config = {"extra": "allow"}


class CourseModule(BaseModel):
    """Módulo (actividad/recurso) dentro de una sección del curso"""
    id: int
    url: Optional[str] = None
    name: str = ""
    instance: Optional[int] = None
    contextid: Optional[int] = None
    description: Optional[str] = None
    visible: Optional[int] = 1
    uservisible: Optional[bool] = True
    visibleoncoursepage: Optional[int] = 1
    modicon: Optional[str] = None
    modname: Optional[str] = None  # "resource", "folder", "url", "assign", etc.
    modplural: Optional[str] = None
    indent: Optional[int] = None
    onclick: Optional[str] = None
    afterlink: Optional[str] = None
    customdata: Optional[str] = None
    noviewlink: Optional[bool] = None
    completion: Optional[int] = None
    completiondata: Optional[dict] = None
    contents: Optional[list[ModuleContent]] = None

    model_config = {"extra": "allow"}

    @property
    def has_downloadable_files(self) -> bool:
        """¿Este módulo tiene archivos descargables?"""
        if not self.contents:
            return False
        return any(
            c.type == "file" and c.fileurl
            for c in self.contents
        )

    @property
    def file_count(self) -> int:
        """Cantidad de archivos descargables"""
        if not self.contents:
            return 0
        return sum(1 for c in self.contents if c.type == "file" and c.fileurl)

    @property
    def total_size(self) -> int:
        """Tamaño total de archivos en bytes"""
        if not self.contents:
            return 0
        return sum(c.filesize or 0 for c in self.contents if c.type == "file")


class CourseSection(BaseModel):
    """Sección (tema) dentro de un curso"""
    id: int
    name: str = ""
    visible: Optional[int] = 1
    summary: Optional[str] = ""
    summaryformat: Optional[int] = None
    section: Optional[int] = None
    hiddenbynumsections: Optional[int] = None
    uservisible: Optional[bool] = True
    modules: list[CourseModule] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @property
    def safe_name(self) -> str:
        """Nombre sanitizado para carpeta"""
        name = self.name or f"Seccion_{self.section or self.id}"
        for char in '<>:"/\\|?*':
            name = name.replace(char, "_")
        return name.strip().rstrip(".")


# ============================================================
# Modelos de respuesta del Bridge
# ============================================================

class BridgeStatus(BaseModel):
    """Estado del servicio bridge"""
    service: str = "MoodleAPI-Bridge"
    status: str = "running"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.now)
    moodle_configured: bool = False
    moodle_connected: bool = False
    google_configured: bool = False
    trello_configured: bool = False
    uptime_seconds: Optional[float] = None


class AuthResponse(BaseModel):
    """Respuesta de autenticación del bridge"""
    success: bool
    message: str
    site_info: Optional[SiteInfo] = None
    error: Optional[str] = None


class CoursesResponse(BaseModel):
    """Respuesta de listado de cursos"""
    success: bool
    message: str
    total_courses: int = 0
    courses: list[Course] = Field(default_factory=list)
    error: Optional[str] = None


class CourseContentsResponse(BaseModel):
    """Respuesta de contenidos de un curso"""
    success: bool
    message: str
    course_id: int
    course_name: str = ""
    total_sections: int = 0
    total_files: int = 0
    sections: list[CourseSection] = Field(default_factory=list)
    error: Optional[str] = None
