import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.core.database import async_session

async def check_plan():
    async with async_session() as session:
        # Check standard explain
        vec_str = str([0.01] * 1536)
        print("=== EXPLAIN with Default Planner Settings ===")
        res = await session.execute(
            text("EXPLAIN SELECT id FROM chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> :v LIMIT 5"),
            {"v": vec_str}
        )
        for row in res:
            print(row[0])

        print("\n=== EXPLAIN with enable_seqscan=off ===")
        await session.execute(text("SET LOCAL enable_seqscan = off;"))
        res = await session.execute(
            text("EXPLAIN SELECT id FROM chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> :v LIMIT 5"),
            {"v": vec_str}
        )
        for row in res:
            print(row[0])

if __name__ == "__main__":
    asyncio.run(check_plan())
