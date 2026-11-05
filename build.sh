#!/usr/bin/env bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Checking SQLite database..."
if [ ! -f "data/uzex.db" ]; then
    echo "Database not found. Building data/uzex.db from raw CSVs..."
    python scripts/build_db.py
else
    echo "Database already exists."
fi

echo "Build complete!"
