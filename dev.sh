#!/bin/bash
# Start local development with shared production DB
# 1. Opens SSH tunnel to production PostgreSQL
# 2. Starts backend + frontend (without local db)
# 3. Cleans up on Ctrl+C

set -e

TUNNEL_PORT=5433
REMOTE_HOST="root@109.199.96.162"

cleanup() {
    echo ""
    echo "Stopping services..."
    docker-compose stop backend frontend 2>/dev/null
    if [ -n "$TUNNEL_PID" ]; then
        kill $TUNNEL_PID 2>/dev/null
        echo "SSH tunnel stopped"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check if tunnel port is already in use
if ss -tln | grep -q ":${TUNNEL_PORT} "; then
    echo "Port ${TUNNEL_PORT} already in use (tunnel already running?)"
else
    echo "Starting SSH tunnel (local:${TUNNEL_PORT} -> prod:5432)..."
    ssh -N -L ${TUNNEL_PORT}:localhost:5432 ${REMOTE_HOST} &
    TUNNEL_PID=$!
    sleep 1

    if ! kill -0 $TUNNEL_PID 2>/dev/null; then
        echo "ERROR: SSH tunnel failed to start"
        exit 1
    fi
    echo "SSH tunnel running (PID: $TUNNEL_PID)"
fi

echo "Starting backend + frontend..."
docker-compose up --build backend frontend
