FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e .

COPY ./src /app/src

CMD ["uvicorn", "voucherbot.main:app", "--host", "0.0.0.0", "--port", "8000"]
