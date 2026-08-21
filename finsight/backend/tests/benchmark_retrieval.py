"""Retrieval Benchmark: Exact pgvector Search vs HNSW Search (Sprint 8.1)."""

import asyncio
import os
import sys
import time
import uuid
from typing import Any
from pathlib import Path

# Add backend root to sys.path so 'app' module is importable
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.embedding_service import EmbeddingService, FakeGenAIClient
from app.services.retrieval_service import RetrievalService

settings = get_settings()

BENCHMARK_QUERIES = [
    "total revenue operations 2025",
    "gross profit margins and operating income",
    "consolidated balance sheet total assets",
    "current liabilities and accounts payable",
    "net cash provided by operating activities",
    "capital expenditures and investments",
    "stockholders equity and retained earnings",
    "income tax expense and effective tax rate",
    "research and development operating expenses",
    "selling general and administrative expenses",
    "commercial paper and short term borrowings",
    "long term debt maturities and interest",
    "depreciation and amortization expenses",
    "diluted earnings per share calculations",
    "dividends declared and share repurchases",
    "operating leases and right of use assets",
    "foreign currency exchange rate fluctuations",
    "contingencies litigation and commitments",
    "segment reporting and geographic revenue",
    "restructuring charges and impairment",
]


async def populate_benchmark_corpus(
    db: AsyncSession,
    embedding_service: EmbeddingService,
    num_docs: int = 10,
    chunks_per_doc: int = 15,
) -> list[uuid.UUID]:
    """Create a synthetic financial corpus of chunks with deterministic embeddings."""
    doc_ids = []
    texts = []
    
    financial_topics = [
        "Consolidated Statements of Operations Revenue $1,000 Gross Profit $400 Net Income $150 in fiscal year 2025",
        "Consolidated Balance Sheets Total Assets $1,500 Cash $300 Total Liabilities $600 Equity $900 in 2025",
        "Statements of Cash Flows Net Cash provided by Operating Activities $300 Capex $100 in 2025",
        "Note 1: Summary of Significant Accounting Policies and revenue recognition standards",
        "Note 2: Financial Instruments Fair Value Measurements and derivative assets",
        "Note 3: Debt Financing and Credit Facilities with weighted average interest rate 4.5%",
        "Note 4: Income Taxes provision and deferred tax liabilities analysis",
        "Note 5: Leases right of use assets and lease liabilities obligations",
        "Note 6: Commitments and Contingencies legal proceedings update",
        "Note 7: Segment Information revenue by geographic region Americas Europe Asia",
        "Management Discussion and Analysis of Financial Condition liquidity and capital resources",
        "Market Risk Disclosures interest rate sensitivity and foreign exchange exposure",
        "Controls and Procedures disclosure controls and internal control over financial reporting",
        "Executive Compensation base salary annual bonus and equity incentive plan",
        "Security Ownership of Certain Beneficial Owners and Management share counts",
    ]

    for d_idx in range(num_docs):
        doc_id = uuid.uuid4()
        doc_ids.append(doc_id)
        doc = Document(
            id=doc_id,
            filename=f"benchmark_doc_{d_idx+1}.pdf",
            file_type="pdf",
            file_size=25000,
            status="indexed",
            total_chunks=chunks_per_doc,
        )
        db.add(doc)

        for c_idx in range(chunks_per_doc):
            t_idx = (d_idx + c_idx) % len(financial_topics)
            content = f"Doc {d_idx+1} Section {c_idx+1}: {financial_topics[t_idx]} [variation {d_idx*10+c_idx}]"
            texts.append((doc_id, c_idx, content))

    await db.flush()

    # Generate embeddings in batches
    raw_texts = [t[2] for t in texts]
    vectors = await embedding_service.embed_texts(raw_texts)

    for (doc_id, c_idx, content), vector in zip(texts, vectors):
        chunk = Chunk(
            document_id=doc_id,
            content=content,
            chunk_type="table" if "Statements" in content or "Sheets" in content else "text",
            chunk_index=c_idx,
            page_number=(c_idx // 3) + 1,
            metadata_={"statement_type": "income_statement" if "Revenue" in content else "narrative"},
            embedding=vector,
        )
        db.add(chunk)

    await db.commit()
    return doc_ids


async def run_benchmark(
    top_k: int = settings.RETRIEVAL_BENCHMARK_TOP_K,
    num_queries: int = settings.RETRIEVAL_BENCHMARK_QUERIES,
) -> dict[str, Any]:
    """
    Executes Mode A (Exact pgvector sequential scan) vs Mode B (HNSW index scan) across benchmark queries.
    Computes latency percentiles, overlap, and Recall@K.
    """
    fake_client = FakeGenAIClient()
    embedding_service = EmbeddingService(client=fake_client)
    retrieval_service = RetrievalService(embedding_service=embedding_service)

    async with async_session() as session:
        # Populate corpus
        doc_ids = await populate_benchmark_corpus(session, embedding_service, num_docs=5, chunks_per_doc=15)

    queries_to_run = BENCHMARK_QUERIES[:num_queries]

    # Pre-generate query vectors so we benchmark DB retrieval only, eliminating API latency
    query_vectors = [await embedding_service.embed_query(q) for q in queries_to_run]

    exact_latencies: list[float] = []
    hnsw_latencies: list[float] = []
    recalls: list[float] = []
    overlaps: list[float] = []

    async with async_session() as session:
        for q_idx, (q_text, q_vec) in enumerate(zip(queries_to_run, query_vectors)):
            # --- Mode A: Exact search (disable HNSW for this transaction) ---
            await session.execute(text("SET LOCAL enable_indexscan = off;"))
            await session.execute(text("SET LOCAL enable_bitmapscan = off;"))
            
            t0 = time.perf_counter()
            exact_results = await retrieval_service.search(query=q_text, top_k=top_k, min_similarity=0.0, db=session)
            t_exact = (time.perf_counter() - t0) * 1000.0  # ms
            exact_latencies.append(t_exact)
            exact_ids = set(r.chunk_id for r in exact_results)

            # --- Mode B: HNSW search (enable index scans + set ef_search) ---
            await session.execute(text("SET LOCAL enable_indexscan = on;"))
            await session.execute(text("SET LOCAL enable_bitmapscan = on;"))
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {settings.HNSW_EF_SEARCH};"))

            t0 = time.perf_counter()
            hnsw_results = await retrieval_service.search(query=q_text, top_k=top_k, min_similarity=0.0, db=session)
            t_hnsw = (time.perf_counter() - t0) * 1000.0  # ms
            hnsw_latencies.append(t_hnsw)
            hnsw_ids = set(r.chunk_id for r in hnsw_results)

            # Calculate Recall@K
            intersection = len(exact_ids.intersection(hnsw_ids))
            recall = intersection / float(len(exact_ids)) if exact_ids else 1.0
            overlap = intersection / float(top_k) if top_k else 1.0

            recalls.append(recall)
            overlaps.append(overlap)

    # Cleanup benchmark docs
    async with async_session() as session:
        for d_id in doc_ids:
            doc_obj = await session.get(Document, d_id)
            if doc_obj:
                await session.delete(doc_obj)
        await session.commit()

    def calc_percentiles(lats: list[float]) -> tuple[float, float, float]:
        sorted_lats = sorted(lats)
        avg = sum(sorted_lats) / len(sorted_lats)
        p50 = sorted_lats[len(sorted_lats) // 2]
        p95 = sorted_lats[int(len(sorted_lats) * 0.95)]
        return avg, p50, p95

    exact_avg, exact_p50, exact_p95 = calc_percentiles(exact_latencies)
    hnsw_avg, hnsw_p50, hnsw_p95 = calc_percentiles(hnsw_latencies)
    avg_recall = sum(recalls) / len(recalls) if recalls else 1.0
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 1.0

    return {
        "num_queries": len(queries_to_run),
        "top_k": top_k,
        "exact": {
            "avg_ms": round(exact_avg, 3),
            "p50_ms": round(exact_p50, 3),
            "p95_ms": round(exact_p95, 3),
        },
        "hnsw": {
            "avg_ms": round(hnsw_avg, 3),
            "p50_ms": round(hnsw_p50, 3),
            "p95_ms": round(hnsw_p95, 3),
        },
        "recall_at_k": round(avg_recall, 4),
        "overlap": round(avg_overlap, 4),
    }


if __name__ == "__main__":
    res = asyncio.run(run_benchmark())
    print("\n==================================================")
    print("FINSIGHT HNSW RETRIEVAL BENCHMARK RESULTS")
    print("==================================================")
    print(f"Total Queries Evaluated: {res['num_queries']} (Top-K = {res['top_k']})")
    print(f"Exact Search Latency : Avg={res['exact']['avg_ms']}ms | P50={res['exact']['p50_ms']}ms | P95={res['exact']['p95_ms']}ms")
    print(f"HNSW Search Latency  : Avg={res['hnsw']['avg_ms']}ms | P50={res['hnsw']['p50_ms']}ms | P95={res['hnsw']['p95_ms']}ms")
    print(f"Average Recall@{res['top_k']}     : {res['recall_at_k'] * 100.0:.2f}% (Target: {settings.RETRIEVAL_RECALL_TARGET * 100:.1f}%)")
    print(f"Average Result Overlap: {res['overlap'] * 100.0:.2f}%")
    print("==================================================\n")
