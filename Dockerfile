FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY app/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code and initialization script
COPY app/ .
COPY app/init_db.sh /usr/local/bin/

# Make the script executable
RUN chmod +x /usr/local/bin/init_db.sh

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    FLASK_APP=/app/app:create_app \
    FLASK_ENV=development \
    PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Set the entrypoint to our initialization script
ENTRYPOINT ["/usr/local/bin/init_db.sh"]

WORKDIR /

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "-", "--error-logfile", "-", "app.app:create_app()"]