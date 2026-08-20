import time
import uuid
import logging
from typing import Any

from sqlalchemy import select

from app.core.database import async_session
from app.core.config import get_settings
from app.core.exceptions import ProcessingError
from app.models.document import Document
from app.services.pdf_parser import PDFParserService
from app.services.text_parser import TextParserService
from app.services.csv_parser import CSVParserService

logger = logging.getLogger("finsight.worker.tasks")
settings = get_settings()


async def process_document(ctx: dict[str, Any], document_id_str: str) -> dict[str, Any]:
    """
    Ingestion task orchestration for Sprint 3.1 & 3.2.
    Loads Document, transitions to 'processing', invokes the appropriate parser
    (PDFParserService, TextParserService, CSVParserService), updates total_pages and metadata,
    and advances status to 'parsed'.
    """
    job_id = ctx.get("job_id", "unknown")
    start_time = time.perf_counter()

    try:
        doc_uuid = uuid.UUID(document_id_str)
    except ValueError:
        logger.error("Invalid document UUID format '%s' in job [%s]", document_id_str, job_id)
        return {"status": "error", "message": "Invalid UUID format"}

    logger.info("Processing document [id=%s, job_id=%s]", doc_uuid, job_id)

    async with async_session() as session:
        try:
            result = await session.execute(
                select(Document).where(Document.id == doc_uuid)
            )
            document = result.scalar_one_or_none()

            if not document:
                logger.warning("Document with ID '%s' not found in database [job_id=%s]", doc_uuid, job_id)
                return {"status": "not_found", "document_id": str(doc_uuid)}

            # Idempotency guard: only transition if currently in 'pending' status
            if document.status != "pending":
                logger.info(
                    "Document '%s' already in status '%s' (skipping duplicate processing) [job_id=%s]",
                    doc_uuid,
                    document.status,
                    job_id,
                )
                return {
                    "status": "skipped",
                    "document_id": str(doc_uuid),
                    "current_status": document.status,
                }

            # State transition 1: pending -> processing
            document.status = "processing"
            document.processing_error = None
            await session.commit()

            # Locate stored document file on disk
            file_path = settings.DOCUMENTS_PATH / f"{doc_uuid}_{document.filename}"

            if document.file_type == "pdf":
                parser = PDFParserService()
                parsed_doc = parser.extract_text_and_metadata(file_path=file_path, document_id=str(doc_uuid))
            elif document.file_type == "txt":
                txt_parser = TextParserService()
                parsed_doc = txt_parser.extract_text_and_metadata(file_path=file_path, document_id=str(doc_uuid))
            elif document.file_type == "csv":
                csv_parser = CSVParserService()
                parsed_doc = csv_parser.extract_text_and_metadata(file_path=file_path, document_id=str(doc_uuid))
            else:
                raise ProcessingError(f"Unsupported file type: {document.file_type}")

            # Update metadata from parsed document
            document.total_pages = parsed_doc.total_pages
            if not document.title and parsed_doc.metadata.get("title"):
                document.title = parsed_doc.metadata["title"]

            # State transition 2: processing -> parsed
            document.status = "parsed"
            document.processing_error = None
            await session.commit()

            duration = time.perf_counter() - start_time
            logger.info(
                "Successfully parsed %s document '%s' (%d pages) in %.4fs [job_id=%s]",
                document.file_type.upper(),
                doc_uuid,
                parsed_doc.total_pages,
                duration,
                job_id,
            )

            return {
                "status": "parsed",
                "document_id": str(doc_uuid),
                "filename": document.filename,
                "file_type": document.file_type,
                "total_pages": parsed_doc.total_pages,
                "duration_seconds": round(duration, 4),
            }

        except Exception as exc:
            await session.rollback()
            logger.exception("Failed to process document '%s' in job [%s]: %s", doc_uuid, job_id, exc)

            # Record failure state on document record
            try:
                result = await session.execute(
                    select(Document).where(Document.id == doc_uuid)
                )
                doc_to_fail = result.scalar_one_or_none()
                if doc_to_fail:
                    doc_to_fail.status = "failed"
                    doc_to_fail.processing_error = str(exc)[:500]
                    await session.commit()
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
