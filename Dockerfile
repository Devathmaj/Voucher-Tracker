FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

CMD ["uvicorn", "voucherbot.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
