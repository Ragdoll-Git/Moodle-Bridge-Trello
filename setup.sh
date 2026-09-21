#!/bin/sh
# ==============================================================================
# MoodleAPI-Bridge — Script de Instalación para Proxmox LXC (Debian/Ubuntu/Alpine)
# ==============================================================================
# Este script automatiza la configuración de la aplicación en contenedores LXC.
# Detecta automáticamente el sistema operativo (Debian/Ubuntu con Systemd, u
# Alpine con OpenRC) y crea el servicio de inicio correspondiente.
#
# Al ser un repositorio PRIVADO, debés clonar primero el repo dentro del LXC
# usando tus credenciales de GitHub y luego ejecutar este script localmente:
#
#   git clone https://github.com/tu-usuario/MoodleAPI-Bridge.git /opt/moodle-bridge
#   cd /opt/moodle-bridge
#   chmod +x setup.sh
#   ./setup.sh
# ==============================================================================

set -e

INSTALL_DIR="/opt/moodle-bridge"
SERVICE_NAME="moodle-bridge"

echo "=== Iniciando Instalación de MoodleAPI-Bridge ==="

# 1. Detectar Distribución
if [ -f /etc/alpine-release ]; then
    OS="alpine"
    echo "Sistema operativo detectado: Alpine Linux"
elif [ -f /etc/debian_version ] || [ -f /etc/lsb-release ]; then
    OS="debian"
    echo "Sistema operativo detectado: Debian/Ubuntu"
else
    OS="unknown"
    echo "Sistema operativo no reconocido. Se asumirá Debian/Ubuntu."
fi

# 2. Instalar dependencias del sistema según la distribución
if [ "$OS" = "alpine" ]; then
    echo "Instalando dependencias usando apk..."
    # Instalar herramientas de compilación básicas para evitar fallos con uvicorn[standard]/uvloop
    apk update
    apk add --no-cache python3 python3-dev py3-pip git bash openrc build-base musl-dev
else
    echo "Instalando dependencias usando apt..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git curl
fi

# 3. Asegurar que estamos en el directorio de instalación
if [ "$(pwd)" != "$INSTALL_DIR" ]; then
    echo "Configurando directorio de instalación en $INSTALL_DIR..."
    if [ ! -d "$INSTALL_DIR" ]; then
        mkdir -p "$INSTALL_DIR"
        # Mover archivos si se ejecutó desde otro lugar
        cp -r ./* "$INSTALL_DIR/" || true
    fi
    cd "$INSTALL_DIR"
fi

# 4. Crear entorno virtual de Python e instalar requerimientos
echo "Configurando entorno virtual de Python (venv)..."
python3 -m venv .venv
echo "Instalando paquetes de Python requeridos..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 5. Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    echo "Creando plantilla de configuración .env..."
    cat <<EOT > .env
# ========================================
# MoodleAPI-Bridge — Configuración LXC
# ========================================

# --- Moodle ---
MOODLE_BASE_URL=https://tu-campus.ejemplo.edu/moodle
MOODLE_USERNAME=tu_dni
MOODLE_PASSWORD=tu_password

# --- Servicio ---
BRIDGE_PORT=8000
BRIDGE_HOST=0.0.0.0   # Permite conexiones externas dentro de la red del LXC

# --- Rate Limiting ---
REQUEST_DELAY=1.5
MAX_RETRIES=3

# --- Trello ---
TRELLO_API_KEY=tu_api_key
TRELLO_TOKEN=tu_token
TRELLO_DEFAULT_BOARD_NAME=Facu
TRELLO_REQUEST_DELAY=0.1
EOT
    echo "   [!] IMPORTANTE: Se creó un archivo .env base en $INSTALL_DIR/.env"
    echo "       Asegurate de editarlo con tus credenciales reales antes de iniciar el servicio."
else
    echo "Archivo .env existente detectado. Manteniendo configuración."
fi

# 6. Crear el servicio de inicio según el gestor de servicios (Systemd o OpenRC)
if [ "$OS" = "alpine" ]; then
    echo "Configurando servicio OpenRC en /etc/init.d/$SERVICE_NAME..."
    
    cat <<'EOT' > "/etc/init.d/$SERVICE_NAME"
#!/sbin/openrc-run

name="moodle-bridge"
description="MoodleAPI-Bridge FastAPI Service"

command="/opt/moodle-bridge/.venv/bin/python"
command_args="-m uvicorn main:app --host 0.0.0.0 --port 8000"
command_background="yes"
directory="/opt/moodle-bridge"
pidfile="/run/moodle-bridge.pid"
start_stop_daemon_args="--stdout /var/log/moodle-bridge.log --stderr /var/log/moodle-bridge.log"

depend() {
    need net
}
EOT

    # Asegurar permisos de ejecución en OpenRC
    chmod +x "/etc/init.d/$SERVICE_NAME"

    # Configurar tarea de cron horaria para sincronización
    echo "Configurando sincronización automática por cron (horaria)..."
    CRON_SCRIPT="/etc/periodic/hourly/moodle-trello-sync"
    cat <<'EOF' > "$CRON_SCRIPT"
#!/bin/sh
# Sincronización automática horaria Moodle -> Trello
date >> /var/log/moodle-trello-sync.log
curl -s -X POST http://localhost:8000/api/trello/sync >> /var/log/moodle-trello-sync.log 2>&1
EOF
    chmod +x "$CRON_SCRIPT"

    # Habilitar crond
    rc-update add crond default || true
    rc-service crond start || true
    
    echo "===================================================================="
    echo "✓ Instalación completada en Alpine Linux."
    echo "===================================================================="
    echo "Siguientes pasos obligatorios para activar el Bridge:"
    echo "  1. Editá el archivo de configuración con tus credenciales reales:"
    echo "     nano $INSTALL_DIR/.env"
    echo ""
    echo "  2. Habilitá y arrancá el servicio de OpenRC y cron:"
    echo "     rc-update add $SERVICE_NAME default"
    echo "     rc-service $SERVICE_NAME start"
    echo ""
    echo "  3. Para verificar el estado o ver los logs en tiempo real:"
    echo "     rc-service $SERVICE_NAME status"
    echo "     tail -f /var/log/moodle-bridge.log"
    echo "     tail -f /var/log/moodle-trello-sync.log"
    echo "===================================================================="

else
    echo "Configurando servicio Systemd en /etc/systemd/system/$SERVICE_NAME.service..."
    
    cat <<EOT > "/etc/systemd/system/$SERVICE_NAME.service"
[Unit]
Description=MoodleAPI-Bridge FastAPI Service
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOT

    # Recargar systemd
    systemctl daemon-reload

    # Configurar tarea de cron horaria para sincronización
    echo "Configurando sincronización automática por cron (horaria)..."
    CRON_FILE="/etc/cron.d/moodle-bridge"
    cat <<'EOF' > "$CRON_FILE"
# Sincronización automática horaria Moodle -> Trello
0 * * * * root date >> /var/log/moodle-trello-sync.log && curl -s -X POST http://localhost:8000/api/trello/sync >> /var/log/moodle-trello-sync.log 2>&1
EOF
    chmod 644 "$CRON_FILE"

    # Asegurar que cron esté habilitado y corriendo
    systemctl enable cron || true
    systemctl start cron || true
 
    echo "===================================================================="
    echo "✓ Instalación completada en Debian/Ubuntu."
    echo "===================================================================="
    echo "Siguientes pasos obligatorios para activar el Bridge:"
    echo "  1. Editá el archivo de configuración con tus credenciales reales:"
    echo "     nano $INSTALL_DIR/.env"
    echo ""
    echo "  2. Habilitá y arrancá el servicio de systemd y cron:"
    echo "     systemctl enable $SERVICE_NAME"
    echo "     systemctl start $SERVICE_NAME"
    echo ""
    echo "  3. Para verificar el estado o ver los logs en tiempo real:"
    echo "     systemctl status $SERVICE_NAME"
    echo "     journalctl -u $SERVICE_NAME -f"
    echo "     tail -f /var/log/moodle-trello-sync.log"
    echo "===================================================================="
fi
