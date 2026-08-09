FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required for pg or chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt
# Copy the backend code
COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
