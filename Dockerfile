# Production Dockerfile for ChaosFit on Google Cloud Run
FROM python:3.11-slim

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0

# Create app directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY backend/requirements.txt ./backend/

# Install uv for efficient package management
RUN pip install --no-cache-dir uv

# Install Python dependencies
RUN uv pip install --system -r backend/requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY .env.example .env

# Create static files directory if it doesn't exist
RUN mkdir -p backend/static

# Copy static files
COPY backend/static/ ./backend/static/

# Set proper permissions
RUN chmod -R 755 backend/

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Run the application with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
