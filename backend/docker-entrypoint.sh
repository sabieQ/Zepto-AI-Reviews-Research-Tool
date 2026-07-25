#!/bin/sh
set -e
# Apply schema before serving traffic (safe if already at head).
alembic upgrade head
exec "$@"
