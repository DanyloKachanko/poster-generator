#!/bin/bash
# SSH tunnel to production PostgreSQL on Coolify
# Maps local port 5433 -> production postgres port 5432
#
# Usage: ./tunnel.sh
# Then set DATABASE_URL=postgresql://poster:poster@localhost:5433/poster_generator

echo "Starting SSH tunnel to production DB (local:5433 -> coolify:5432)..."
echo "Press Ctrl+C to stop"
ssh -N -L 5433:localhost:5432 root@109.199.96.162
