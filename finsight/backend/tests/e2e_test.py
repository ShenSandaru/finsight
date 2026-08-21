"""End-to-end integration test runner for Sprint 3.1, 3.2, 4.1, 4.2 & 5.1 (PDF, TXT, CSV, Table Extraction, Semantics, and Chunk Persistence)."""

import io
import json
import time
import uuid
import asyncio
import urllib.request
import sys
import os
from pathlib import Path

# Ensure app package is discoverable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject

from sqlalchemy import select
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings
from app.models.chunk import Chunk


def make_pdf(pages_text: list[str], metadata: dict[str, str] | None = None) -> bytes:
    writer = PdfWriter()
    font_dict = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    font_ref = writer._add_object(font_dict)

    for text in pages_text:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        if text:
            stream_content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin-1")
            stream_obj = DecodedStreamObject()
            stream_obj.set_data(stream_content)
            page[NameObject("/Contents")] = writer._add_object(stream_obj)

    if metadata:
        formatted_meta = {("/" + k if not k.startswith("/") else k): v for k, v in metadata.items()}
        writer.add_metadata(formatted_meta)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_pdf_with_tables(
    pages_tables: list[tuple[str, list[list[str]]]],
    metadata: dict[str, str] | None = None,
) -> bytes:
    """Generate a multi-page PDF with explicit grid lines and text cells for table detection."""
    writer = PdfWriter()
    font_dict = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    font_ref = writer._add_object(font_dict)

    for page_text, table_rows in pages_tables:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })

        stream_cmds = []
        if page_text:
            lines = page_text.split("\n")
            curr_y = 720
            for l in lines:
                safe_text = l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                stream_cmds.append(f"BT /F1 12 Tf 72 {curr_y} Td ({safe_text}) Tj ET")
                curr_y -= 16

        if table_rows:
            num_rows = len(table_rows)
            num_cols = max(len(r) for r in table_rows)
            x_start, y_start = 72, 620
            col_width = 450 / max(1, num_cols)
            row_height = 25

            stream_cmds.append("0.5 w 0 G")
            for r in range(num_rows + 1):
                y = y_start - (r * row_height)
                stream_cmds.append(f"{x_start} {y} m {x_start + (num_cols * col_width)} {y} l S")
            for c in range(num_cols + 1):
                x = x_start + (c * col_width)
                stream_cmds.append(f"{x} {y_start} m {x} {y_start - (num_rows * row_height)} l S")

            for r_idx, row in enumerate(table_rows):
                for c_idx, cell_val in enumerate(row):
                    if cell_val:
                        safe_val = str(cell_val).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                        x = x_start + (c_idx * col_width) + 5
                        y = y_start - (r_idx * row_height) - 18
                        stream_cmds.append(f"BT /F1 10 Tf {x} {y} Td ({safe_val}) Tj ET")

        stream_content = "\n".join(stream_cmds).encode("latin-1")
        stream_obj = DecodedStreamObject()
        stream_obj.set_data(stream_content)
        page[NameObject("/Contents")] = writer._add_object(stream_obj)

    if metadata:
        formatted_meta = {("/" + k if not k.startswith("/") else k): v for k, v in metadata.items()}
        writer.add_metadata(formatted_meta)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def upload_multipart(filename: str, content: bytes, content_type: str = "application/pdf") -> dict:
    boundary = "----FinSightTestBoundary98765"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("latin-1") + content + f"\r\n--{boundary}--\r\n".encode("latin-1")
    
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/documents/upload", data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_document(doc_id: str) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:8000/api/v1/documents/{doc_id}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def poll_document(doc_id: str, timeout: int = 10) -> dict:
    for _ in range(timeout * 2):
        time.sleep(0.5)
        doc = get_document(doc_id)
        if doc["status"] in ("parsed", "failed"):
            return doc
    return get_document(doc_id)


async def verify_document_chunks_in_db(doc_id_str: str):
    """Verify that chunks were correctly persisted in PostgreSQL with NULL embeddings."""
    doc_uuid = uuid.UUID(doc_id_str)
    settings = get_settings()
    isolated_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    isolated_session = async_sessionmaker(bind=isolated_engine, class_=AsyncSession, expire_on_commit=False)

    async with isolated_session() as session:
        result = await session.execute(select(Chunk).where(Chunk.document_id == doc_uuid).order_by(Chunk.chunk_index))
        chunks = result.scalars().all()
        assert len(chunks) > 0, f"Expected chunks > 0 for document {doc_id_str}"
        for c in chunks:
            assert c.embedding is not None, f"Chunk {c.id} should have embedding populated"
            assert len(c.embedding) == 1536, f"Chunk {c.id} vector dimension must be 1536, got {len(c.embedding)}"
            assert c.chunk_type in ("text", "table"), f"Unexpected chunk_type '{c.chunk_type}'"
            assert c.page_number is not None, f"Chunk {c.id} missing page_number"
            assert isinstance(c.metadata_, dict), f"Chunk {c.id} metadata must be a dict"
        print(f"  -> Database verification: {len(chunks)} Chunk records in PostgreSQL (embedding=1536-dim vector confirmed).")
        await isolated_engine.dispose()
        return chunks


async def verify_hnsw_index_in_db():
    """Verify that the HNSW index is active and valid in PostgreSQL system catalogs."""
    from app.services.vector_index_service import VectorIndexService
    settings = get_settings()
    isolated_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    isolated_session = async_sessionmaker(bind=isolated_engine, class_=AsyncSession, expire_on_commit=False)

    async with isolated_session() as session:
        info = await VectorIndexService.get_hnsw_index_info(db=session)
        assert info.exists is True, "HNSW index does not exist in PostgreSQL"
        assert info.index_method == "hnsw", f"Expected method 'hnsw', got '{info.index_method}'"
        assert info.opclass_name == "vector_cosine_ops", f"Expected 'vector_cosine_ops', got '{info.opclass_name}'"
        assert info.is_valid is True, "HNSW index is marked invalid in pg_index"
        print("  -> PostgreSQL catalog verification: HNSW index 'ix_chunks_embedding_hnsw_cosine' is ACTIVE & VALID.")
        await isolated_engine.dispose()


def search_retrieval(query: str, top_k: int = 5, min_similarity: float = 0.0, document_id: str | None = None) -> dict:
    payload = {
        "query": query,
        "top_k": top_k,
        "min_similarity": min_similarity,
        "document_id": document_id,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/search", data=body)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def query_rag(query: str, top_k: int = 5, min_similarity: float = 0.30, document_id: str | None = None) -> dict:
    payload = {
        "query": query,
        "top_k": top_k,
        "min_similarity": min_similarity,
        "document_id": document_id,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/rag/query", data=body)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_e2e_tests():
    print("==================================================")
    print("STARTING E2E INTEGRATION & PIPELINE VERIFICATION")
    print("==================================================")

    # 1. Valid 2-page PDF test
    print("\n[E2E 1] Uploading 2-page valid PDF with metadata...")
    pdf_bytes = make_pdf(
        ["Page 1: Annual Revenue 2025", "Page 2: Consolidated Balance Sheet"],
        {"Title": "Apple 10-K Fiscal 2025"}
    )
    up_resp = upload_multipart("apple_10k_2025.pdf", pdf_bytes)
    doc_id = up_resp["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp['document']['status']} (id={doc_id})")
    assert up_resp["document"]["status"] == "pending", f"Expected initial 'pending', got {up_resp['document']['status']}"

    doc = poll_document(doc_id)
    print(f"  -> Final Status: {doc['status']}, Total Pages: {doc['total_pages']}, Total Chunks: {doc.get('total_chunks')}, Title: '{doc['title']}', Error: {doc['processing_error']}")
    assert doc["status"] == "indexed", f"Expected 'indexed', got {doc['status']}"
    assert doc["total_pages"] == 2, f"Expected total_pages=2, got {doc['total_pages']}"
    assert doc.get("total_chunks") == 2, f"Expected total_chunks=2, got {doc.get('total_chunks')}"
    assert doc["title"] == "Apple 10-K Fiscal 2025", f"Expected title set from metadata, got {doc['title']}"
    assert doc["processing_error"] is None, f"Expected null processing_error, got {doc['processing_error']}"
    asyncio.run(verify_document_chunks_in_db(doc_id))
    print("  ✅ E2E 1 PASSED: Valid PDF processed, chunked, and indexed with 1536-dim embeddings.")

    # 2. Malformed PDF test (magic bytes valid %PDF- header, broken structure)
    print("\n[E2E 2] Uploading malformed PDF (valid %PDF- header, broken structure)...")
    corrupt_bytes = b"%PDF-1.7\nCorrupted binary bytes that cause pypdf to fail."
    up_resp_corrupt = upload_multipart("corrupt_doc.pdf", corrupt_bytes)
    corrupt_id = up_resp_corrupt["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp_corrupt['document']['status']} (id={corrupt_id})")

    doc_corrupt = poll_document(corrupt_id)
    print(f"  -> Final Status: {doc_corrupt['status']}, Processing Error: '{doc_corrupt['processing_error']}'")
    assert doc_corrupt["status"] == "failed", f"Expected 'failed', got {doc_corrupt['status']}"
    assert doc_corrupt["processing_error"] is not None, "Expected populated processing_error"
    print("  ✅ E2E 2 PASSED: Malformed PDF cleanly handled pending -> processing -> failed.")

    # 3. TXT file upload test (Sprint 3.2 Full Parsing Flow + Sprint 5.1 Chunking + Sprint 6.1 Embeddings)
    print("\n[E2E 3] Uploading plain text (.txt) file...")
    txt_bytes = b"FinSight Earnings Summary\nQ3 Revenue reached $2.5 billion with 18% YoY growth."
    up_resp_txt = upload_multipart("earnings_summary.txt", txt_bytes, content_type="text/plain")
    txt_id = up_resp_txt["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp_txt['document']['status']} (id={txt_id})")
    assert up_resp_txt["document"]["status"] == "pending", f"Expected initial 'pending', got {up_resp_txt['document']['status']}"

    doc_txt = poll_document(txt_id)
    print(f"  -> Final Status: {doc_txt['status']}, Total Pages: {doc_txt['total_pages']}, Total Chunks: {doc_txt.get('total_chunks')}, Error: {doc_txt['processing_error']}")
    assert doc_txt["status"] == "indexed", f"Expected 'indexed', got {doc_txt['status']}"
    assert doc_txt["total_pages"] == 1, f"Expected total_pages=1 for TXT, got {doc_txt['total_pages']}"
    assert doc_txt.get("total_chunks") == 1, f"Expected total_chunks=1 for TXT, got {doc_txt.get('total_chunks')}"
    assert doc_txt["processing_error"] is None, f"Expected null processing_error, got {doc_txt['processing_error']}"
    asyncio.run(verify_document_chunks_in_db(txt_id))
    print("  ✅ E2E 3 PASSED: TXT file parsed, chunked, and indexed with 1536-dim embeddings.")

    # 4. Financial PDF with Statement Tables (Sprint 4.1, 4.2, 5.1 & 6.1 Table-Aware Embedding Verification)
    print("\n[E2E 4] Uploading Financial PDF with Income Statement, Balance Sheet, and Cash Flow tables...")
    financial_pdf_bytes = make_pdf_with_tables(
        [
            (
                "Consolidated Statements of Operations\nYears Ended December 31, 2025",
                [
                    ["Financial Metric", "2025", "2024"],
                    ["Total Revenue", "$1,000", "$900"],
                    ["Gross Profit", "$400", "$360"],
                    ["Net Income", "$150", "$130"],
                ]
            ),
            (
                "Consolidated Balance Sheets\nAs of December 31, 2025",
                [
                    ["Item", "2025", "2024"],
                    ["Total Assets", "$1,500", "$1,350"],
                    ["Total Liabilities", "$600", "$550"],
                    ["Total Stockholders Equity", "$900", "$800"],
                ]
            ),
            (
                "Statements of Cash Flows\nYears Ended December 31, 2025",
                [
                    ["Cash Flow Activity", "2025", "2024"],
                    ["Net Cash Provided by Operating Activities", "$300", "$280"],
                    ["Capital Expenditures", "$100", "$90"],
                ]
            ),
        ],
        {"Title": "Financial Statements 2025"}
    )
    up_resp_fin = upload_multipart("financial_statements_2025.pdf", financial_pdf_bytes)
    fin_id = up_resp_fin["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp_fin['document']['status']} (id={fin_id})")
    assert up_resp_fin["document"]["status"] == "pending", f"Expected initial 'pending', got {up_resp_fin['document']['status']}"

    doc_fin = poll_document(fin_id)
    print(f"  -> Final Status: {doc_fin['status']}, Total Pages: {doc_fin['total_pages']}, Total Chunks: {doc_fin.get('total_chunks')}, Title: '{doc_fin['title']}', Error: {doc_fin['processing_error']}")
    assert doc_fin["status"] == "indexed", f"Expected 'indexed', got {doc_fin['status']}"
    assert doc_fin["total_pages"] == 3, f"Expected total_pages=3, got {doc_fin['total_pages']}"
    assert doc_fin.get("total_chunks") >= 3, f"Expected total_chunks>=3, got {doc_fin.get('total_chunks')}"
    assert doc_fin["processing_error"] is None, f"Expected null processing_error, got {doc_fin['processing_error']}"

    chunks = asyncio.run(verify_document_chunks_in_db(fin_id))
    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    text_chunks = [c for c in chunks if c.chunk_type == "text"]
    assert len(table_chunks) > 0, "Expected table chunks to be generated"
    assert len(text_chunks) > 0, "Expected text chunks to be generated"
    
    # Verify table semantic metadata fields on table chunks
    for tc in table_chunks:
        assert "table_id" in tc.metadata_, "Table chunk missing table_id"
        assert "statement_type" in tc.metadata_, "Table chunk missing statement_type"
        assert "fiscal_periods" in tc.metadata_, "Table chunk missing fiscal_periods"
        print(f"    -> Table chunk verified: type={tc.metadata_.get('statement_type')}, periods={tc.metadata_.get('fiscal_periods')}")

    print("  ✅ E2E 4 PASSED: Multi-page Financial PDF chunked and indexed with text + semantic table embeddings.")

    # 5. Vector Similarity Search & Retrieval (Sprint 6.2 & 8.1 HNSW Verification)
    print("\n[E2E 5] Verifying HNSW Vector Index and Executing Vector Similarity Search against indexed Financial PDF...")
    asyncio.run(verify_hnsw_index_in_db())
    search_queries = [
        "revenue gross profit operations",
        "balance sheet assets liabilities",
        "cash flows operating activities",
    ]

    for q in search_queries:
        search_res = search_retrieval(query=q, top_k=5, min_similarity=0.0, document_id=fin_id)
        assert search_res["query"] == q, f"Query mismatch: expected '{q}', got '{search_res['query']}'"
        assert search_res["total_results"] > 0, f"Expected > 0 results for query '{q}'"
        results = search_res["results"]
        
        # Verify descending order of similarity
        similarities = [r["similarity"] for r in results]
        assert similarities == sorted(similarities, reverse=True), f"Results not sorted by similarity descending: {similarities}"
        
        # Verify contract preservation
        for item in results:
            assert item["chunk_id"] is not None
            assert item["document_id"] == fin_id
            assert item["chunk_type"] in ("text", "table")
            assert item["page_number"] is not None
            assert 0.0 <= item["similarity"] <= 1.0
            assert isinstance(item["metadata"], dict)
            if item["chunk_type"] == "table":
                assert "statement_type" in item["metadata"]
                assert "fiscal_periods" in item["metadata"]
        
        print(f"  -> Search query '{q}': retrieved {len(results)} chunks (top match similarity: {results[0]['similarity']:.4f}, type: {results[0]['chunk_type']})")

    print("  ✅ E2E 5 PASSED: In-database pgvector similarity search, descending ordering, and metadata preservation verified.")

    # 6. Grounded RAG Question Answering (Sprint 7.1 Verification)
    print("\n[E2E 6] Executing Grounded RAG Question Answering against indexed Financial PDF...")
    rag_queries = [
        "What was the total revenue in 2025?",
        "What were total assets on the balance sheet?",
        "What was net cash provided by operating activities?",
    ]

    for rq in rag_queries:
        rag_res = query_rag(query=rq, top_k=5, min_similarity=0.30, document_id=fin_id)
        assert rag_res["query"] == rq, f"Query mismatch: expected '{rq}', got '{rag_res['query']}'"
        assert rag_res["grounded"] is True, f"Expected grounded=True for relevant query '{rq}'"
        assert len(rag_res["answer"]) > 0, f"Expected non-empty answer for query '{rq}'"
        assert len(rag_res["citations"]) > 0, f"Expected citations for query '{rq}'"
        assert rag_res["retrieved_chunks"] >= 1
        
        for cit in rag_res["citations"]:
            assert cit["chunk_id"] is not None
            assert cit["document_id"] == fin_id
            assert cit["page_number"] is not None
            assert cit["chunk_type"] in ("text", "table")
            assert 0.0 <= cit["similarity"] <= 1.0
            if cit["chunk_type"] == "table":
                assert cit["statement_type"] in ("income_statement", "balance_sheet", "cash_flow", None)
                assert isinstance(cit["fiscal_periods"], list)

        print(f"  -> RAG query '{rq}': grounded answer generated with {len(rag_res['citations'])} citations (top citation page: {rag_res['citations'][0]['page_number']}, statement: {rag_res['citations'][0]['statement_type']})")

    print("  ✅ E2E 6 PASSED: Grounded RAG answer generation, context assembly, and structured citation verification passed.")

    print("\n==================================================")
    print("ALL END-TO-END TESTS PASSED SUCCESSFULLY! 🎉")
    print("==================================================")


if __name__ == "__main__":
    run_e2e_tests()


