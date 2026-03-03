#!/bin/bash
set -e

echo "Applying knowledge DB migrations..."
alembic -c alembic_articles.ini upgrade head

echo "Starting loader scheduler..."
exec python3 -m loader.scheduler
