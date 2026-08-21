
import time
import uuid
import logging
from typing import Any
from collections import Counter

from sqlalchemy import select, delete

from app.core.database import async_session
from app.core.config import get_settings
from app.core.exceptions import ProcessingError
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.pdf_parser import PDFParserService
from app.services.text_parser import TextParserService
from app.services.csv_parser import CSVParserService
from app.services.table_extractor import TableExtractorService
from app.services.table_semantics import FinancialTableSemanticService, StatementType
from app.services.chunker import TableAwareChunkerService

logger = logging.getLogger("finsight.worker.tasks")
settings = get_settings()


async def process_document(ctx: dict[str, Any], document_id_str: str) -> dict[str, Any]:
    """
    Ingestion task orchestration for Sprint 3.1, 3.2, 4.1, 4.2 & 5.1.
    Loads Document, transitions to 'processing', invokes the appropriate parser
    (PDFParserService, TextParserService, CSVParserService), extracts & semantically enriches
    tables for PDFs, generates structured text & table chunks via TableAwareChunkerService,
    atomically persists Chunk records (with embedding=None), updates total_pages and total_chunks,
    and advances status to 'parsed'.
    """
    job_id = ctx.get("job_id", "unknown")
    try:
        doc_uuid = uuid.UUID(document_id_str)
    except ValueError:
        logger.error("Invalid document UUID format '%s' in job [%s]", document_id_str, job_id)
        return {"status": "error", "message": "Invalid UUID format"}

    logger.info("Processing document [id=%s, job_id=%s]", doc_uuid, job_id)
    start_time = time.perf_counter()

    async with async_session() as session:
        try:
            # Fetch document record
            stmt = select(Document).where(Document.id == doc_uuid)
            result = await session.execute(stmt)
            document = result.scalar_one_or_none()

            if not document:
                logger.warning("Document with ID '%s' not found in database [job_id=%s]", doc_uuid, job_id)
                return {"status": "not_found", "document_id": str(doc_uuid)}

            # Idempotency guard: only transition if currently in 'pending' status
            if document.status != "pending":
                logger.info("Document '%s' already in status '%s' (skipping duplicate processing) [job_id=%s]", doc_uuid, document.status, job_id)
                return {"status": "skipped", "document_id": str(doc_uuid), "current_status": document.status}

            # State transition 1: pending -> processing
            document.status = "processing"
            document.processing_error = None
            await session.commit()

            # Locate stored document file on disk
            file_path = settings.DOCUMENTS_PATH / f"{doc_uuid}_{document.filename}"

            table_count = 0
            statement_counts: dict[str, int] = {}
            extracted_tables = []

            if document.file_type == "pdf":
                parser = PDFParserService()
                parsed_doc = parser.extract_text_and_metadata(file_path=file_path, document_id=str(doc_uuid))

                # Extract financial tables
                table_extractor = TableExtractorService()
                extracted_tables = table_extractor.extract_tables_from_pdf(file_path=file_path, document_id=str(doc_uuid))
                table_count = len(extracted_tables)

                # Enrich tables with semantic classification & period context
                semantic_service = FinancialTableSemanticService()
                for tbl in extracted_tables:
                    tbl.semantics = semantic_service.analyze_table(tbl)

                raw_counts = Counter(tbl.semantics.statement_type for tbl in extracted_tables if tbl.semantics)
                statement_counts = dict(raw_counts)

            elif document.file_type == "txt":
                txt_parser = TextParserService()
                parsed_doc = txt_parser.extract_text_and_metadata(file_path=file_path, document_id=str(doc_uuid))
            elif document.file_type == "csv":
                csv_parser = CSVParserService()
                parsed_doc = csv_parser.extract_text_and_metadata(file_path=file_path, document_id=str(doc_uuid))
            else:
                raise ProcessingError(f"Unsupported file type: {document.file_type}")

            # Generate Chunks (Sprint 5.1 - TableAwareChunkerService)
            chunker = TableAwareChunkerService()
            chunks_data = chunker.create_chunks(parsed_doc, extracted_tables)

            # Atomic database transaction:
            # 1. Delete existing chunks for this document (idempotency/retry safety)
            await session.execute(delete(Chunk).where(Chunk.document_id == doc_uuid))

            # 2. Bulk insert newly generated Chunk ORM records
            db_chunks = [
                Chunk(
                    document_id=doc_uuid,
                    content=c.content,
                    chunk_type=c.chunk_type,
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    metadata_=c.metadata,
                    embedding=None,
                )
                for c in chunks_data
            ]
            session.add_all(db_chunks)

            # 3. Update document metadata and transition status
            document.total_pages = parsed_doc.total_pages
            document.total_chunks = len(chunks_data)
            if not document.title and parsed_doc.metadata.get("title"):
                document.title = parsed_doc.metadata["title"]

            # State transition 2: processing -> parsed
            document.status = "parsed"
            document.processing_error = None
            await session.commit()

            duration = time.perf_counter() - start_time
            if document.file_type == "pdf":
                logger.info(
                    "Successfully processed PDF document '%s' (%d pages, %d tables extracted [Income Statements: %d, Balance Sheets: %d, Cash Flows: %d, Unknown: %d], %d chunks created) in %.4fs [job_id=%s]",
                    doc_uuid,
                    parsed_doc.total_pages,
                    table_count,
                    statement_counts.get(StatementType.INCOME_STATEMENT, 0),
                    statement_counts.get(StatementType.BALANCE_SHEET, 0),
                    statement_counts.get(StatementType.CASH_FLOW, 0),
                    statement_counts.get(StatementType.UNKNOWN, 0),
                    len(chunks_data),
                    duration,
                    job_id,
                )
            else:
                logger.info(
                    "Successfully processed %s document '%s' (%d pages, %d chunks created) in %.4fs [job_id=%s]",
                    document.file_type.upper(),
                    doc_uuid,
                    parsed_doc.total_pages,
                    len(chunks_data),
                    duration,
                    job_id,
                )

            return {
                "status": "parsed",
                "document_id": str(doc_uuid),
                "filename": document.filename,
                "file_type": document.file_type,
                "total_pages": parsed_doc.total_pages,
                "total_chunks": len(chunks_data),
                "tables_extracted": table_count,
                "duration_seconds": round(duration, 4),
            }

        except Exception as exc:
            await session.rollback()
            logger.exception("Failed to process document '%s' in job [%s]: %s", doc_uuid, job_id, exc)

            # Two-phase transaction error recovery: NEW transaction to record failure state
            try:
                async with async_session() as err_session:
                    result = await err_session.execute(
                        select(Document).where(Document.id == doc_uuid)
                    )
                    doc_to_fail = result.scalar_one_or_none()
                    if doc_to_fail:
                        doc_to_fail.status = "failed"
                        doc_to_fail.processing_error = str(exc)[:500]
                        await err_session.commit()
            except Exception as inner_exc:
                logger.error("Could not record failed status for document '%s': %s", doc_uuid, inner_exc)

            raise


async def health_check_task(ctx: dict[str, Any], message: str) -> dict[str, Any]:
    """
    Test / Demo task to verify ARQ background worker and Redis infrastructure.
    """
    job_id = ctx.get("job_id", "unknown")
    start_time = time.perf_counter()
    logger.info("Executing health_check_task [job_id=%s] with message='%s'", job_id, message)

    # Perform lightweight verification logic
    duration = time.perf_counter() - start_time
    result = {
        "status": "success",
        "job_id": job_id,
        "received_message": message,
        "duration_seconds": round(duration, 5),
    }

    logger.info("Completed health_check_task [job_id=%s] in %.5fs", job_id, duration)
    return result


async def failing_test_task(ctx: dict[str, Any], error_reason: str) -> None:
    """
    Test task designed to fail to verify worker error handling and process resilience.
    """
    job_id = ctx.get("job_id", "unknown")
    logger.warning("Executing failing_test_task [job_id=%s] - deliberate error: %s", job_id, error_reason)
    raise RuntimeError(f"Deliberate test failure: {error_reason}")
