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
