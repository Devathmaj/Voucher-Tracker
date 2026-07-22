FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

CMD sh -c "uvicorn voucherbot.main:app --host 0.0.0.0 --port ${PORT:-8000}"
