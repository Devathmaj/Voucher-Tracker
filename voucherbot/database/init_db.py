from voucherbot.database.connection import engine
from voucherbot.models.base import Base
from sqlalchemy import Connection

import voucherbot.models.source  # noqa: F401
import voucherbot.models.post  # noqa: F401 — Post only; VoucherPost is a view
import voucherbot.models.keyword  # noqa: F401
import voucherbot.models.event  # noqa: F401
import voucherbot.models.pipeline_lock  # noqa: F401


async def init_db() -> None:
    def _create_all(sync_conn: Connection) -> None:
        tables = [
            table
            for table in Base.metadata.sorted_tables
            if not table.info.get("is_view")
        ]
        Base.metadata.create_all(sync_conn, tables=tables)

    async with engine.begin() as conn:
        await conn.run_sync(_create_all)
