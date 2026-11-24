#!/bin/sh
# Configuración inicial (UNA sola vez) de la EC2 Ubuntu 24.04.
# Uso, ya conectado por SSH:
#   curl -fsSL https://raw.githubusercontent.com/<usuario>/<repo>/main/scripts/setup_ec2.sh | sh -s https://github.com/<usuario>/<repo>.git
set -e

REPO_URL="${1:?uso: setup_ec2.sh <url del repositorio .git>}"
APP_DIR="$HOME/sa-v2"

echo ">> Instalando Docker Engine + Compose"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git
if ! command -v docker > /dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

echo ">> Swap de 2 GB (la instancia corre app + OpenObserve + Grafana + Prometheus)"
if ! sudo swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab > /dev/null
fi

echo ">> Clonando el repositorio en $APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
fi

echo ""
echo ">> Listo. Pasos siguientes:"
echo "   1. nano $APP_DIR/.env          (cambiar TODAS las contraseñas)"
echo "   2. exit  y volver a entrar por SSH (para usar docker sin sudo)"
echo "   3. cd $APP_DIR && GIT_SHA=\$(git rev-parse HEAD) docker compose up -d --build"
