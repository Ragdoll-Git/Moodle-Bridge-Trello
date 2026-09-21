# MoodleAPI-Bridge 🔌

Bridge de integración y automatización entre la API de Moodle y servicios externos (Trello).

Servicio desarrollado en FastAPI que actúa como un puente entre tu campus virtual Moodle y tu tablero de Trello. Permite extraer tus materias, secciones, archivos y sincronizar todas las tareas y foros pendientes a Trello de forma automática.

---

## ✨ Características Clave

* **Autenticación Automática**: Inicio de sesión automático y seguro utilizando tu usuario y contraseña de Moodle.
* **Sincronización Inteligente con Trello**:
  * **Idempotencia**: Si vuelves a sincronizar, actualiza los datos de las tarjetas existentes (descripción, fecha de entrega) en lugar de duplicarlas.
  * **Detección de Entrega**: Mapea el estado de entrega en Moodle; si ya entregaste una tarea, la marca automáticamente con el check verde de completada en Trello.
  * **Evita Rellenar Tableros**: Si la tarea ya fue entregada en Moodle antes de sincronizar por primera vez, no creará la tarjeta en Trello para evitar ruidos molestos.
  * **Organización Personalizada**: Al actualizar tarjetas, no les altera la lista actual. Esto te permite mover tarjetas a listas personalizadas (ej. *En Progreso*, *Hacer*) y el bridge respetará tu organización.
  * **Listas Archivadas**: Si archivas una lista completa de una materia en Trello, el bridge detecta que está archivada y omite esa materia de la sincronización.
* **Dashboard Web Moderno**: Interfaz oscura premium para monitorear el estado de las conexiones, ver tus cursos, revisar el historial de logs en tiempo real y gatillar acciones.
* **Sincronización Periódica (Cron)**: Tareas de cron horarias pre-configuradas para mantener Trello al día automáticamente.
* **Actualizador de Código Web**: Botón integrado en el panel para hacer `git pull` de GitHub y reiniciar el servicio de forma automática con un solo clic.

---

## 🚀 Instalación y Configuración

### Opción A: Despliegue Automatizado en Proxmox LXC (Recomendado)
El proyecto incluye un instalador automatizado (`setup.sh`) compatible con **Alpine Linux (OpenRC)** y **Debian/Ubuntu (Systemd)**.

1. Clona el repositorio privado dentro de tu LXC usando tu clave SSH:
   ```bash
   git clone git@github.com:tu-usuario/MoodleAPI-Bridge.git /opt/moodle-bridge
   cd /opt/moodle-bridge
   ```
2. Otorga permisos y ejecuta el instalador:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
3. Edita el archivo de configuración `.env` generado:
   ```bash
   nano /opt/moodle-bridge/.env
   ```
4. Habilita e inicia los servicios:
   * **Alpine Linux**:
     ```bash
     rc-update add moodle-bridge default
     rc-service moodle-bridge start
     ```
   * **Debian/Ubuntu**:
     ```bash
     systemctl enable moodle-bridge
     systemctl start moodle-bridge
     ```

### Opción B: Instalación Local (Desarrollo)
```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/MoodleAPI-Bridge.git
cd MoodleAPI-Bridge

# 2. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# 3. Instalar requerimientos
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env   # Windows
cp .env.example .env     # Linux/macOS
# Editar .env con tus credenciales

# 5. Iniciar servidor
python main.py
```

---

## ⚙️ Configuración (.env)

El archivo `.env` controla el comportamiento de la aplicación:

| Variable | Descripción | Valor Ejemplo |
|----------|-------------|---------------|
| `MOODLE_BASE_URL` | URL base del campus | `https://tu-campus.ejemplo.edu/moodle` |
| `MOODLE_USERNAME` | Tu DNI de alumno | `12345678` |
| `MOODLE_PASSWORD` | Tu contraseña de aulas | `mi_password` |
| `BRIDGE_HOST` | Host para escuchar peticiones | `0.0.0.0`  |
| `BRIDGE_PORT` | Puerto de escucha | `8000` |
| `REQUEST_DELAY` | Delay para peticiones Moodle | `1.5` (segundos para evitar rate-limits) |
| `MAX_RETRIES` | Reintentos ante fallas de red | `3` |
| `TRELLO_API_KEY` | Key de Desarrollador de Trello | `tu_api_key` |
| `TRELLO_TOKEN` | Token de usuario de Trello | `tu_token` |
| `TRELLO_DEFAULT_BOARD_NAME` | Tablero destino | `tu_tablero` |
| `TRELLO_REQUEST_DELAY` | Delay para peticiones Trello | `0.1` (segundos) |

---

## 📡 API Endpoints

El servicio expone una API REST interactiva en `/docs` (Swagger UI) y `/redoc` (ReDoc):

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/health` | Estado de conexión con Moodle, Trello y uptime. |
| `POST` | `/api/moodle/auth` | Realiza la autenticación manual e inicia sesión. |
| `GET` | `/api/moodle/courses` | Lista las materias matriculadas. |
| `GET` | `/api/moodle/courses/{id}/contents` | Detalles, temas y archivos de una materia. |
| `GET` | `/api/trello/boards` | Lista los tableros disponibles en tu cuenta de Trello. |
| `GET` | `/api/trello/status` | Verifica y diagnostica la conexión a la API de Trello. |
| `POST` | `/api/trello/sync` | Gatilla la sincronización inteligente de Moodle a Trello. |
| `POST` | `/api/system/update` | Realiza un `git pull` y reinicia el servicio automáticamente. |

---

## 📅 Sincronización Automática (Cron)

El instalador `setup.sh` configura una tarea horaria en el sistema para mantener Trello actualizado sin intervención humana:

* **En Alpine (OpenRC)**: Crea un script en `/etc/periodic/hourly/moodle-trello-sync`.
* **En Debian/Ubuntu (Systemd)**: Agrega la regla en `/etc/cron.d/moodle-bridge`.
* **Logs del Cron**: Se pueden inspeccionar las ejecuciones en tiempo real corriendo:
  ```bash
  tail -f /var/log/moodle-trello-sync.log
  ```

---

## 🔄 Actualización Remota del Servidor

Para actualizar el bridge a la última versión directamente desde el panel de control web:
1. Asegúrate de que el LXC esté configurado usando autenticación por **Clave SSH sin frase de contraseña** contra GitHub (para que el comando no se bloquee pidiendo contraseña en segundo plano).
2. Presiona el botón **Actualizar Código** en el dashboard.
3. El panel descargará las últimas modificaciones de GitHub y reiniciará el servicio en segundo plano, reconectándose automáticamente una vez que vuelva a estar en línea.

---

## 🧪 Pruebas Unitarias

La suite de pruebas simula las APIs de Moodle y Trello para asegurar que los flujos de sincronización, modelos y endpoints funcionen correctamente.

```bash
.venv\Scripts\pytest tests/ -v
```
*Los registros detallados se guardan en la carpeta `tests/logs/test_output.log`.*

---

## 📋 Roadmap

- [x] Autenticación y sesión persistente con Moodle.
- [x] Obtención de cursos y contenidos del campus.
- [x] Dashboard Web de monitoreo en tiempo real.
- [x] Integración bidireccional inteligente con Trello (idempotencia y detección de entregas).
- [x] Instalador automatizado para Proxmox LXC (Debian/Ubuntu/Alpine).
- [x] Sincronización horaria automatizada por Cron.
- [x] Actualizador de sistema y reinicio automático integrado en la web.
- [ ] Integración con Google Drive para descarga automática de archivos de cursos *(próximamente)*.
