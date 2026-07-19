# Prefer 3.12+ (local bot venv may still be 3.9; API routes avoid 3.10+| syntax)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-saas.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-saas.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
