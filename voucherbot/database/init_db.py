from voucherbot.database.connection import engine
from voucherbot.models.base import Base

import voucherbot.models.source  # noqa: F401
import voucherbot.models.post  # noqa: F401
import voucherbot.models.alert  # noqa: F401

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
