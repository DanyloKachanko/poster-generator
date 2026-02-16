#!/bin/bash
# Start local development with shared production DB
# Tunnel runs as a Docker service (profile: dev)
# Ctrl+C stops everything

set -e

echo "Starting tunnel + backend + frontend..."
docker-compose --profile dev up --build backend frontend
