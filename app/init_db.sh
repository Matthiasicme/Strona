#!/bin/bash
set -e

# ----------------------------
# init_db.sh — wait for Postgres, run migrations, then start the server
# ----------------------------

echo "Waiting for PostgreSQL to be ready..."
until PGPASSWORD="$POSTGRES_PASSWORD" psql -h "postgres" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
  echo "PostgreSQL is unavailable - retrying in 1s..."
  sleep 1
done

echo "PostgreSQL is up! Applying database migrations..."

# Export PYTHONPATH to ensure imports work correctly
export PYTHONPATH=/app:$PYTHONPATH

echo "Current directory: $(pwd)"
echo "Python path: $PYTHONPATH"
echo "Flask app: $FLASK_APP"

# Initialize migrations if not already done
if [ ! -d "migrations" ]; then
    echo "Initializing migrations..."
    flask db init
    echo "Migrations initialized."
fi

# Create migration and upgrade
echo "Creating database migration..."
flask db migrate -m "Initial migration"
echo "Applying database migrations..."
flask db upgrade

echo "Migrations applied successfully."

# Initialize the database with sample data if it's empty
if [ "$INIT_DB_WITH_SAMPLE_DATA" = "true" ]; then
    echo "Initializing database with sample data..."
    python /app/init_db.py
    echo "Sample data initialization completed."
fi

echo "Launching application..."

# Exec any CMD from the Dockerfile (i.e. gunicorn ...)
exec "$@"
