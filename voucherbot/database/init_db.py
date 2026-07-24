from voucherbot.database.connection import engine
from voucherbot.models.base import Base
from sqlalchemy import Connection, text

import voucherbot.models.source  # noqa: F401
import voucherbot.models.post  # noqa: F401 — Post only; VoucherPost is a view
import voucherbot.models.keyword  # noqa: F401
import voucherbot.models.event  # noqa: F401
import voucherbot.models.pipeline_lock  # noqa: F401
import voucherbot.models.vendor_mapping  # noqa: F401

_NEW_ENUM_VALUES = ["PEARSONVUE", "TRAINING_PROVIDER"]


async def _ensure_source_type_enum() -> None:
    """Add new SourceType enum values if they don't exist yet.

    ALTER TYPE ... ADD VALUE cannot run inside a transaction, so we use
    a raw connection with autocommit.
    """
    from sqlalchemy import inspect

    async with engine.connect() as conn:
        await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        try:
            result = await conn.execute(
                text("SELECT unnest(enum_range(NULL::sourcetype))::text AS val")
            )
            existing = {row[0] for row in result}
        except Exception:
            existing = set()

        for val in _NEW_ENUM_VALUES:
            if val not in existing:
                await conn.execute(text(f"ALTER TYPE sourcetype ADD VALUE '{val}'"))
                await conn.commit()


async def init_db() -> None:
    await _ensure_source_type_enum()

    def _create_all(sync_conn: Connection) -> None:
        tables = [
            table
            for table in Base.metadata.sorted_tables
            if not table.info.get("is_view")
        ]
        Base.metadata.create_all(sync_conn, tables=tables)

    async with engine.begin() as conn:
        await conn.run_sync(_create_all)
