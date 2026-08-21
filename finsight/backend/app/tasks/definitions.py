
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
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger("finsight.worker.tasks")
settings = get_settings()


async def process_document(ctx: dict[str, Any], document_id_str: str) -> dict[str, Any]:
    """
    Ingestion task orchestration for Sprint 3.1, 3.2, 4.1, 4.2, 5.1 & 6.1.
    Loads Document, transitions to 'processing', invokes the appropriate parser,
    extracts & semantically enriches tables for PDFs, generates structured chunks,
    persists Chunk records (parsed), generates 1536-dimensional Gemini embeddings
    outside of DB transactions, atomically persists embeddings, and advances status to 'indexed'.
    """
    job_id = ctx.get("job_id", "unknown")
    try:
        doc_uuid = uuid.UUID(document_id_str)
    except ValueError:
        logger.error("Invalid document UUID format '%s' in job [%s]", document_id_str, job_id)
        return {"status": "error", "message": "Invalid UUID format"}

    logger.info("Processing document [id=%s, job_id=%s]", doc_uuid, job_id)
    start_time = time.perf_counter()

    # Step 1: Parsing & Chunk Persistence Transaction (processing -> parsed)
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

        except Exception as exc:
            await session.rollback()
            logger.exception("Failed during parsing/chunking for document '%s' in job [%s]: %s", doc_uuid, job_id, exc)

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

    # Step 2: Query Stored Chunks (Read Only, Closed Immediately)
    async with async_session() as read_session:
        result = await read_session.execute(
            select(Chunk).where(Chunk.document_id == doc_uuid).order_by(Chunk.chunk_index)
        )
        persisted_chunks = result.scalars().all()

    # Zero-chunk handling (Rule 16)
    if not persisted_chunks:
        logger.error("No chunks available for embedding for document '%s' [job_id=%s]", doc_uuid, job_id)
        async with async_session() as err_session:
            result = await err_session.execute(select(Document).where(Document.id == doc_uuid))
            doc_to_fail = result.scalar_one_or_none()
            if doc_to_fail:
                doc_to_fail.status = "failed"
                doc_to_fail.processing_error = "No chunks available for embedding"
                await err_session.commit()
        raise ProcessingError("No chunks available for embedding", details={"document_id": str(doc_uuid)})

    # Idempotency check: if all chunks already have non-null embeddings, skip generation
    if all(c.embedding is not None for c in persisted_chunks):
        logger.info("All chunks already have embeddings for document '%s' (preserving indexed status) [job_id=%s]", doc_uuid, job_id)
        async with async_session() as update_session:
            result = await update_session.execute(select(Document).where(Document.id == doc_uuid))
            doc_obj = result.scalar_one_or_none()
            if doc_obj and doc_obj.status != "indexed":
                doc_obj.status = "indexed"
                doc_obj.processing_error = None
                await update_session.commit()
        return {
            "status": "indexed",
            "document_id": str(doc_uuid),
            "total_chunks": len(persisted_chunks),
            "embedded_chunks": len(persisted_chunks),
            "duration_seconds": round(time.perf_counter() - start_time, 4),
        }

    # Step 3: Generate Gemini Embeddings (NO DB Transaction Open - Rule A)
    embedding_service = EmbeddingService()
    try:
        paired_embeddings = await embedding_service.embed_chunks(persisted_chunks)
    except Exception as exc:
        logger.exception("Failed during Gemini embedding generation for document '%s' in job [%s]: %s", doc_uuid, job_id, exc)
        await embedding_service.close()
        # Safe failure recording transaction
        async with async_session() as err_session:
            result = await err_session.execute(select(Document).where(Document.id == doc_uuid))
            doc_to_fail = result.scalar_one_or_none()
            if doc_to_fail:
                doc_to_fail.status = "failed"
                # Strip out any possible secrets
                safe_err = str(exc).replace(settings.GEMINI_API_KEY, "[REDACTED]") if settings.GEMINI_API_KEY else str(exc)
                doc_to_fail.processing_error = safe_err[:500]
                await err_session.commit()
        raise
    finally:
        await embedding_service.close()

    # Step 4: Atomic DB Persistence Transaction (Rule B & Rule 17)
    async with async_session() as persist_session:
        try:
            # Map chunk_id to embedding vector
            vec_map = {chunk_id: vector for chunk_id, vector in paired_embeddings}
            for chunk_obj in persisted_chunks:
                vec = vec_map.get(chunk_obj.id)
                if vec is None or len(vec) != settings.EMBEDDING_DIMENSIONS:
                    raise ProcessingError(f"Missing or invalid vector for chunk {chunk_obj.id}")
                
                # Update chunk record
                res = await persist_session.execute(select(Chunk).where(Chunk.id == chunk_obj.id))
                db_chunk = res.scalar_one()
                db_chunk.embedding = vec

            # Update document record
            doc_res = await persist_session.execute(select(Document).where(Document.id == doc_uuid))
            doc_to_index = doc_res.scalar_one()
            doc_to_index.status = "indexed"
            doc_to_index.processing_error = None
            await persist_session.commit()

        except Exception as exc:
            await persist_session.rollback()
            logger.exception("Failed during embedding persistence for document '%s' in job [%s]: %s", doc_uuid, job_id, exc)

            async with async_session() as err_session:
                result = await err_session.execute(select(Document).where(Document.id == doc_uuid))
                doc_to_fail = result.scalar_one_or_none()
                if doc_to_fail:
                    doc_to_fail.status = "failed"
                    doc_to_fail.processing_error = str(exc)[:500]
                    await err_session.commit()
            raise

    duration = time.perf_counter() - start_time
    logger.info(
        "Successfully indexed document '%s' (%d chunks, 1536-dim embeddings generated) in %.4fs [job_id=%s]",
        doc_uuid,
        len(persisted_chunks),
        duration,
        job_id,
    )

    return {
        "status": "indexed",
        "document_id": str(doc_uuid),
        "filename": document.filename if 'document' in locals() and document else "",
        "file_type": document.file_type if 'document' in locals() and document else "",
        "total_pages": document.total_pages if 'document' in locals() and document else None,
        "total_chunks": len(persisted_chunks),
        "embedded_chunks": len(paired_embeddings),
        "duration_seconds": round(duration, 4),
    }


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


async def generate_financial_report(ctx: dict[str, Any], report_id_str: str) -> dict[str, Any]:
    """
    Asynchronous ARQ background task for generating structured financial research reports (Sprint 10.4).
    1. Loads Report record from PostgreSQL and transitions to 'processing'.
    2. Invokes the verified multi-agent research workflow (FinancialResearchService.execute_research).
    3. Compiles structured GitHub Flavored Markdown report.
    4. Validates output via Guardrails ResponseGuard.
    5. Persists findings, citations, executive summary, full markdown content, and marks status='completed'.
    6. On failure, cleanly records sanitized error message and sets status='failed'.
    """
    from app.models.report import Report
    from app.agents.graph import FinancialResearchService
    from app.services.report_service import ReportService
    from app.guardrails.response_guard import ResponseGuard

    job_id = ctx.get("job_id", "unknown")
    try:
        rep_uuid = uuid.UUID(report_id_str)
    except ValueError:
        logger.error("Invalid report UUID format '%s' in job [%s]", report_id_str, job_id)
        return {"status": "error", "message": "Invalid UUID format"}

    logger.info("Starting financial report generation [report_id=%s, job_id=%s]", rep_uuid, job_id)
    start_time = time.perf_counter()

    # Step 1: Transition to processing
    async with async_session() as session:
        result = await session.execute(select(Report).where(Report.id == rep_uuid))
        report = result.scalar_one_or_none()
        if not report:
            logger.warning("Report with ID '%s' not found in database [job_id=%s]", rep_uuid, job_id)
            return {"status": "not_found", "report_id": str(rep_uuid)}

        if report.status != "pending":
            logger.info("Report '%s' already in status '%s' (skipping) [job_id=%s]", rep_uuid, report.status, job_id)
            return {"status": "skipped", "report_id": str(rep_uuid), "current_status": report.status}

        report.status = "processing"
        report.error_message = None
        await session.commit()
        query_text = report.query
        doc_ids_raw = report.document_ids
        report_title = report.title

    # Parse document_ids if provided
    scoped_doc_ids = None
    if doc_ids_raw:
        scoped_doc_ids = [uuid.UUID(str(d)) for d in doc_ids_raw]

    # Step 2: Execute Verified Financial Research DAG (1 Gemini synthesis call inside SynthesisNode)
    try:
        research_service = FinancialResearchService()
        research_state = await research_service.execute_research(
            query=query_text,
            document_ids=scoped_doc_ids,
        )

        # Step 3: Compile Markdown Report
        markdown_content = ReportService.compile_markdown_report(
            title=report_title,
            query=query_text,
            state=research_state,
        )

        # Step 4: Validate via Guardrails
        guardrails_result = research_state.get("guardrails_validation")
        if not guardrails_result:
            guardrails_result = ResponseGuard.validate(
                query=query_text,
                answer=research_state.get("final_answer", ""),
                citations=research_state.get("citations", []),
                retrieved_chunks=research_state.get("retrieved_chunks", []),
                findings=research_state.get("findings", []),
            )

        # Step 5: Serialize Findings and Citations for DB Storage
        serialized_findings = [f.model_dump(mode="json") for f in research_state.get("findings", [])]
        serialized_citations = [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id) if c.document_id else None,
                "page_number": c.page_number,
                "chunk_type": c.chunk_type,
                "similarity": c.similarity,
                "statement_type": c.statement_type,
                "fiscal_periods": c.fiscal_periods,
            }
            for c in research_state.get("citations", [])
        ]

        # Step 6: Persist Completed Report
        async with async_session() as session:
            result = await session.execute(select(Report).where(Report.id == rep_uuid))
            rep_to_update = result.scalar_one_or_none()
            if rep_to_update:
                rep_to_update.executive_summary = research_state.get("final_answer")
                rep_to_update.findings = serialized_findings
                rep_to_update.content = markdown_content
                rep_to_update.citations = serialized_citations
                rep_to_update.status = "completed" if (guardrails_result and guardrails_result.passed) else "failed"
                if guardrails_result and not guardrails_result.passed:
                    rep_to_update.error_message = "Guardrails validation failed on generated response"
                await session.commit()

        duration = time.perf_counter() - start_time
        logger.info(
            "Successfully completed financial research report '%s' in %.4fs [job_id=%s]",
            rep_uuid,
            duration,
            job_id,
        )
        return {
            "status": "completed",
            "report_id": str(rep_uuid),
            "findings_count": len(serialized_findings),
            "citations_count": len(serialized_citations),
            "duration_seconds": round(duration, 4),
        }

    except Exception as exc:
        duration = time.perf_counter() - start_time
        logger.exception("Failed during report generation for '%s' in job [%s]: %s", rep_uuid, job_id, exc)

        async with async_session() as err_session:
            result = await err_session.execute(select(Report).where(Report.id == rep_uuid))
            rep_to_fail = result.scalar_one_or_none()
            if rep_to_fail:
                rep_to_fail.status = "failed"
                rep_to_fail.error_message = str(exc)[:500]
                await err_session.commit()

        return {
            "status": "failed",
            "report_id": str(rep_uuid),
            "error": str(exc)[:500],
            "duration_seconds": round(duration, 4),
        }
