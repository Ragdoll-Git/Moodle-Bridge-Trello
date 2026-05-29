"""
MoodleAPI-Bridge — Entry Point.

Servidor FastAPI que actúa como bridge entre Moodle
y servicios externos (Google, Trello).

Uso:
    python main.py
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.config import settings
from src.services.bridge import bridge_service
from src.routes import moodle_routes, google_routes, trello_routes

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("moodle-bridge")


# ============================================================
# Lifecycle
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup y shutdown del bridge"""
    logger.info("=" * 60)
    logger.info("  MoodleAPI-Bridge v0.1.0")
    logger.info("=" * 60)
    logger.info(f"  Moodle URL:    {settings.moodle_base_url}")
    logger.info(f"  Moodle user:   {'✓ configurado' if settings.is_moodle_configured else '✗ sin configurar'}")
    logger.info(f"  Google:        {'✓ configurado' if settings.is_google_configured else '○ pendiente'}")
    logger.info(f"  Trello:        {'✓ configurado' if settings.is_trello_configured else '○ pendiente'}")
    logger.info(f"  Rate limit:    {settings.request_delay}s entre requests")
    logger.info(f"  Max retries:   {settings.max_retries}")
    logger.info("=" * 60)

    # Auto-autenticar si las credenciales están configuradas
    if settings.is_moodle_configured:
        logger.info("Credenciales de Moodle detectadas, auto-autenticando...")
        result = bridge_service.moodle_authenticate()
        if result.success:
            logger.info(f"✓ Auto-autenticación exitosa: {result.site_info.fullname if result.site_info else 'N/A'}")
        else:
            logger.warning(f"✗ Auto-autenticación fallida: {result.error}")
    else:
        logger.info("No hay credenciales de Moodle en .env. Usa POST /api/moodle/auth para autenticarte.")

    # Verificar conexión con Trello si está configurado
    if settings.is_trello_configured:
        logger.info("Credenciales de Trello detectadas, verificando conexión...")
        trello_status = bridge_service.trello_get_status()
        if trello_status.get("connected"):
            logger.info(f"✓ Conexión a Trello verificada exitosamente: {trello_status.get('message')}")
        else:
            logger.warning(f"✗ Falló la conexión a Trello: {trello_status.get('message')}")
    else:
        logger.info("No hay credenciales de Trello en .env. Habilita Trello agregando las claves al .env.")

    yield

    # Shutdown
    logger.info("Cerrando MoodleAPI-Bridge...")
    bridge_service.shutdown()
    logger.info("Bridge cerrado correctamente")


# ============================================================
# App
# ============================================================

app = FastAPI(
    title="MoodleAPI-Bridge",
    description=(
        "Bridge entre la API de Moodle y servicios externos "
        "(Google, Trello). Permite consultar cursos, recursos y sincronizar "
        "datos entre plataformas."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============================================================
# Routes
# ============================================================

# Health check
@app.get("/api/health", tags=["System"])
async def health_check():
    """Estado del servicio bridge"""
    status = bridge_service.get_status()
    return status

# Errores recientes
@app.get("/api/errors", tags=["System"])
async def recent_errors():
    """Últimos errores registrados"""
    return {
        "errors": bridge_service.recent_errors,
        "total": len(bridge_service.recent_errors),
    }

# Actualizar servicio desde GitHub
@app.post("/api/system/update", tags=["System"])
async def update_system():
    """Realiza un git pull y reinicia el servicio del bridge"""
    import subprocess
    import threading
    import time
    from src.config import PROJECT_ROOT

    try:
        logger.info("Iniciando actualización del sistema desde GitHub...")
        pull_result = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT)
        )
        logger.info(f"git pull output: {pull_result.stdout}")

        # Programar el reinicio en segundo plano
        def restart_service():
            time.sleep(1)
            if Path("/etc/alpine-release").exists():
                logger.info("Reiniciando servicio moodle-bridge en Alpine...")
                subprocess.run(["rc-service", "moodle-bridge", "restart"])
            else:
                logger.info("Reiniciando servicio moodle-bridge en Debian/Ubuntu...")
                subprocess.run(["systemctl", "restart", "moodle-bridge"])

        threading.Thread(target=restart_service, daemon=True).start()

        return {
            "success": True,
            "message": "Código actualizado con éxito. Reiniciando servicio...",
            "output": pull_result.stdout,
        }
    except subprocess.CalledProcessError as e:
        err_msg = f"Error en git pull (código {e.returncode}): {e.stderr}"
        logger.error(err_msg)
        return {
            "success": False,
            "message": "Error al ejecutar git pull",
            "error": err_msg,
        }
    except Exception as e:
        err_msg = f"Error inesperado: {str(e)}"
        logger.error(err_msg)
        return {
            "success": False,
            "message": "Error inesperado al reiniciar",
            "error": err_msg,
        }

# Routers de servicios
app.include_router(moodle_routes.router)
app.include_router(google_routes.router)
app.include_router(trello_routes.router)

# ============================================================
# Static files (Web UI de monitoreo)
# ============================================================

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_ui():
        """Sirve la interfaz web de monitoreo"""
        return FileResponse(str(static_dir / "index.html"))


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.bridge_host,
        port=settings.bridge_port,
        reload=True,
        log_level="info",
    )
