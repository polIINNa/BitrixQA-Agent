#!/bin/bash
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting the bot..."
exec python telegram_bot/bot.py
