#!/bin/bash
# ==============================================================================
# MoodleAPI-Bridge — Script de Instalación y Despliegue para Proxmox LXC
# ==============================================================================
# Este script automatiza la configuración de la aplicación en un contenedor LXC
# basado en Debian o Ubuntu, creando un servicio de systemd para inicio automático.
#
# Uso en el LXC:
#   curl -sSL https://raw.githubusercontent.com/tu-usuario/MoodleAPI-Bridge/master/setup_lxc.sh | bash
# ==============================================================================

set -e

# Configuración de variables
INSTALL_DIR="/opt/moodle-bridge"
REPO_URL="https://github.com/tu-usuario/MoodleAPI-Bridge.git"
SERVICE_NAME="moodle-bridge"

echo "=== Iniciando Instalación de MoodleAPI-Bridge ==="

# 1. Actualizar el sistema e instalar dependencias básicas
echo "1. Actualizando paquetes e instalando dependencias de Python y Git..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl

# 2. Descargar o actualizar la aplicación en /opt
if [ -d "$INSTALL_DIR" ]; then
    echo "2. Carpeta de instalación existente detectada. Actualizando repositorio..."
    cd "$INSTALL_DIR"
    git fetch --all
    git reset --hard origin/master
else
    echo "2. Clonando repositorio en $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 3. Crear entorno virtual de Python e instalar requerimientos
echo "3. Configurando entorno virtual de Python (venv)..."
python3 -m venv .venv
echo "Instalando paquetes de Python requeridos..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 4. Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    echo "4. Creando plantilla de configuración .env..."
    cat <<EOT > .env
# ========================================
# MoodleAPI-Bridge — Configuración LXC
# ========================================

# --- Moodle ---
MOODLE_BASE_URL=https://moodle.example.edu/itu
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
    echo "4. Archivo .env existente detectado. Manteniendo configuración."
fi

# 5. Crear el servicio de systemd para inicio automático
echo "5. Creando archivo de servicio systemd en /etc/systemd/system/$SERVICE_NAME.service..."
cat <<EOT > /etc/systemd/system/$SERVICE_NAME.service
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

echo "===================================================================="
echo "✓ Instalación del sistema y estructura completada."
echo "===================================================================="
echo "Siguientes pasos obligatorios para activar el Bridge:"
echo "  1. Editá el archivo de configuración con tus credenciales reales:"
echo "     nano $INSTALL_DIR/.env"
echo ""
echo "  2. Habilitá y arrancá el servicio de systemd:"
echo "     systemctl enable $SERVICE_NAME"
echo "     systemctl start $SERVICE_NAME"
echo ""
echo "  3. Para verificar el estado o ver los logs en tiempo real:"
echo "     systemctl status $SERVICE_NAME"
echo "     journalctl -u $SERVICE_NAME -f"
echo "===================================================================="
