# MoodleAPI-Bridge 🔌

Bridge entre la API de Moodle del **Panel de monitoreo** y servicios externos (Google, Trello).

Servicio FastAPI que se conecta al campus virtual (`https://moodle.example.edu/itu/`) usando tus credenciales de alumno, permite consultar cursos y recursos, y expone una API REST para integrar con otros servicios.

## 🚀 Instalación

```bash
# 1. Clonar el repo
git clone https://github.com/TU_USUARIO/MoodleAPI-Bridge.git
cd MoodleAPI-Bridge

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar credenciales
copy .env.example .env
# Editar .env con tu usuario y contraseña de Moodle
```

## ▶️ Uso

```bash
# Iniciar el servicio
python main.py

# Acceder al monitor web
# http://localhost:8000

# Documentación interactiva (Swagger)
# http://localhost:8000/docs
```

## 📡 API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/health` | Estado del servicio |
| `POST` | `/api/moodle/auth` | Autenticar con Moodle |
| `GET` | `/api/moodle/courses` | Listar cursos matriculados |
| `GET` | `/api/moodle/courses/{id}/contents` | Contenidos de un curso |
| `POST` | `/api/google/sync` | Sync con Google Drive *(próximamente)* |
| `POST` | `/api/trello/sync` | Sync con Trello *(próximamente)* |

## 🧪 Tests

```bash
pytest tests/ -v
```

Los logs de tests se guardan en `tests/logs/`.

## 📁 Estructura

```
MoodleAPI-Bridge/
├── main.py              # Entry point FastAPI
├── src/
│   ├── config.py        # Configuración (.env)
│   ├── moodle/          # Cliente API de Moodle
│   ├── routes/          # Endpoints REST
│   └── services/        # Lógica de negocio
├── static/              # Web UI de monitoreo
└── tests/               # Tests + logs
```

## ⚙️ Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MOODLE_BASE_URL` | URL del Moodle | `https://moodle.example.edu/itu` |
| `MOODLE_USERNAME` | Tu DNI / usuario | — |
| `MOODLE_PASSWORD` | Tu contraseña | — |
| `BRIDGE_HOST` | Host del servicio | `0.0.0.0` |
| `BRIDGE_PORT` | Puerto | `8000` |
| `REQUEST_DELAY` | Delay entre requests (seg) | `1.5` |
| `MAX_RETRIES` | Reintentos por request | `3` |

## ⚠️ Seguridad

- **Nunca subas tu `.env`** — está en `.gitignore`
- El token de Moodle equivale a tus credenciales
- El delay entre requests evita saturar el servidor de Moodle
- Solo accedés a tus propios datos de alumno

## 📋 Roadmap

- [x] Autenticación con Moodle
- [x] Listado de cursos
- [x] Contenidos de cursos
- [x] Web UI de monitoreo
- [ ] Descarga de archivos
- [ ] Integración con Google Drive
- [ ] Integración con Trello
- [ ] Deploy en Proxmox (Docker/systemd)
