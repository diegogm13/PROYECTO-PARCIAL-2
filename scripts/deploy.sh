#!/bin/sh
# Se ejecuta EN LA EC2 (lo llama el pipeline por SSH) después de "git reset --hard <sha>".
# Uso: sh scripts/deploy.sh <sha_nuevo> [sha_anterior]
# Reconstruye y actualiza los contenedores; si la versión nueva no responde, regresa a la anterior.
set -e

SHA="${1:?uso: deploy.sh <sha> [sha_anterior]}"
PREV="${2:-}"
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "!! Falta el archivo .env (cp .env.example .env y editar contraseñas)"
  exit 1
fi

up() {
  GIT_SHA="$1" docker compose up -d --build --remove-orphans
}

healthy() {
  for i in $(seq 1 40); do
    if curl -fs http://localhost/api/health | grep -q "$1"; then return 0; fi
    sleep 3
  done
  return 1
}

echo ">> Desplegando commit $SHA"
up "$SHA"

if healthy "$SHA"; then
  echo ">> Despliegue OK: commit $SHA en línea"
  docker compose ps
  docker image prune -f > /dev/null
  exit 0
fi

echo "!! La versión $SHA no respondió en /api/health"
docker compose logs --tail 60 backend nginx || true

if [ -n "$PREV" ] && [ "$PREV" != "$SHA" ]; then
  echo ">> Rollback a $PREV"
  git reset --hard "$PREV"
  up "$PREV"
fi
exit 1
