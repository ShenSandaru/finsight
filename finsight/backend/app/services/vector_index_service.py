"""Vector Index Inspection and Verification Service (Sprint 8.1)."""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session

logger = logging.getLogger("finsight.services.vector_index")

HNSW_INDEX_NAME = "ix_chunks_embedding_hnsw_cosine"


@dataclass
class VectorIndexInfo:
    """Detailed metadata about the chunks table vector index."""
    exists: bool
    index_name: str | None = None
    table_name: str | None = None
    index_method: str | None = None  # e.g., 'hnsw', 'ivfflat'
    column_name: str | None = None
    opclass_name: str | None = None  # e.g., 'vector_cosine_ops'
    is_valid: bool = False
    index_definition: str | None = None


class VectorIndexService:
    """
    Inspects PostgreSQL system catalogs to verify vector index status, validity, and operator classes.
    """

    @classmethod
    async def get_hnsw_index_info(
        cls,
        index_name: str = HNSW_INDEX_NAME,
        db: AsyncSession | None = None,
    ) -> VectorIndexInfo:
        """
        Query pg_indexes, pg_class, pg_index, and pg_opclass for vector index verification.
        """
        query = text(
            """
            SELECT
                c.relname AS index_name,
                t.relname AS table_name,
                am.amname AS index_method,
                i.indisvalid AS is_valid,
                pg_get_indexdef(c.oid) AS index_def,
                op.opcname AS opclass_name
            FROM pg_class c
            JOIN pg_index i ON i.indexrelid = c.oid
            JOIN pg_class t ON t.oid = i.indrelid
            JOIN pg_am am ON am.oid = c.relam
            LEFT JOIN pg_opclass op ON op.oid = ANY(i.indclass)
            WHERE c.relname = :index_name
            LIMIT 1;
            """
        )

        if db is not None:
            res = await db.execute(query, {"index_name": index_name})
            row = res.mappings().first()
        else:
            async with async_session() as session:
                res = await session.execute(query, {"index_name": index_name})
                row = res.mappings().first()

        if not row:
            return VectorIndexInfo(exists=False)

        return VectorIndexInfo(
            exists=True,
            index_name=row["index_name"],
            table_name=row["table_name"],
            index_method=row["index_method"],
            column_name="embedding",
            opclass_name=row["opclass_name"],
            is_valid=bool(row["is_valid"]),
            index_definition=row["index_def"],
        )

    @classmethod
    async def is_hnsw_index_ready(
        cls,
        index_name: str = HNSW_INDEX_NAME,
        db: AsyncSession | None = None,
    ) -> bool:
        """Convenience method checking if HNSW index exists, uses hnsw method, and is marked valid."""
        info = await cls.get_hnsw_index_info(index_name=index_name, db=db)
        return bool(info.exists and info.is_valid and info.index_method == "hnsw")
