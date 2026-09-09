FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade 935deb1afd0f && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
