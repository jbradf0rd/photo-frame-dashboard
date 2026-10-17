#!/usr/bin/env bash
# Build the dashboard and deploy it with the server to a Docker host over SSH.
#   DEPLOY_HOST=mynas DEPLOY_DIR=/srv/family-frame bash deploy.sh
# The host needs Docker Compose and a .env in DEPLOY_DIR (see server/.env.example).
set -euo pipefail
cd "$(dirname "$0")"
HOST="${DEPLOY_HOST:?set DEPLOY_HOST (an ssh host name)}"
DEST="${DEPLOY_DIR:-/srv/family-frame}"
( cd web && npx vite build >/dev/null )
ssh -o BatchMode=yes "$HOST" "mkdir -p $DEST/web $DEST/server $DEST/data"
tar -C web/dist -cf - . | ssh -o BatchMode=yes "$HOST" "rm -rf $DEST/web.new && mkdir -p $DEST/web.new && tar -C $DEST/web.new -xf - && rm -rf $DEST/web.old && mv $DEST/web $DEST/web.old && mv $DEST/web.new $DEST/web"
tar -C server -cf - server.py prayer.py docker-compose.yml | ssh -o BatchMode=yes "$HOST" "tar -C $DEST/server -xf - && mv -f $DEST/server/docker-compose.yml $DEST/docker-compose.yml"
ssh -o BatchMode=yes "$HOST" "cd $DEST && test -f .env && docker compose up -d --force-recreate >/dev/null 2>&1 && sleep 2 && wget -qO- http://127.0.0.1:8098/api/health"
echo
