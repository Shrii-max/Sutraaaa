# Multi-stage Dockerfile for LexAgent
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime image
FROM python:3.11-slim

WORKDIR /app

# Create unprivileged user for security
RUN groupadd -r lexagent && useradd -r -g lexagent -d /app lexagent

# Copy installed python packages from builder
COPY --from=builder /root/.local /home/lexagent/.local
ENV PATH=/home/lexagent/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source
COPY --chown=lexagent:lexagent app/ /app/app/
COPY --chown=lexagent:lexagent scripts/ /app/scripts/
COPY --chown=lexagent:lexagent alembic.ini /app/
COPY --chown=lexagent:lexagent alembic/ /app/alembic/

USER lexagent

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

