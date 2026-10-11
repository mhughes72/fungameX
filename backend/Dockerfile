FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway sets $PORT. The worker service overrides the start command with: python -m app.worker
CMD ["sh", "-c", "uvicorn app.main:app --host '::' --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
