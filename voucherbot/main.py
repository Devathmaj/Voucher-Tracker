from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
import structlog

from voucherbot.api.routers import health, sources, posts, alerts
from voucherbot.config.settings import settings
from voucherbot.core.logging import setup_logging
from voucherbot.services.scheduler import start_scheduler, stop_scheduler

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    await logger.ainfo("Starting up VoucherBot API...", is_prod=settings.is_prod)
    # Non-prod: create tables + seed. Production uses a DML-only DB role, so
    # schema/setup must be applied ahead of time (alembic + admin bootstrap).
    if not settings.is_prod:
        from voucherbot.database.init_db import init_db
        from voucherbot.database.bootstrap import bootstrap_data

        await init_db()
        await bootstrap_data()
    else:
        await logger.ainfo("Skipping DB init/bootstrap (IS_PROD=true)")
    start_scheduler()
    yield
    await stop_scheduler()
    await logger.ainfo("Shutting down VoucherBot API...")

app = FastAPI(
    title="VoucherBot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(sources.router)
app.include_router(posts.router)
app.include_router(alerts.router)
