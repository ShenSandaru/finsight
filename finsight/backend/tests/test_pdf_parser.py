"""Unit and integration tests for PDFParserService and process_document task orchestration (Sprint 3.1 & 3.2)."""

import io
import unittest
import uuid
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from pypdf import PdfWriter
from pypdf.generic import (
    NameObject,
    DictionaryObject,
    DecodedStreamObject,
)

from app.core.exceptions import ProcessingError
from app.services.pdf_parser import PDFParserService, ParsedPage, ParsedDocument
from app.tasks.definitions import process_document
from app.models.document import Document


def generate_test_pdf(
    pages_text: list[str | None],
    metadata: dict[str, str] | None = None,
    password: str | None = None,
) -> bytes:
    """Generate synthetic PDF bytes with font resources and content streams."""
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
        resources = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        page[NameObject("/Resources")] = resources

        if text is not None and len(text) > 0:
            safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_content = f"BT /F1 12 Tf 72 712 Td ({safe_text}) Tj ET".encode("latin-1")
            
            stream_obj = DecodedStreamObject()
            stream_obj.set_data(stream_content)
            page[NameObject("/Contents")] = writer._add_object(stream_obj)

    if metadata:
        formatted_meta = {}
        for k, v in metadata.items():
            key = f"/{k}" if not k.startswith("/") else k
            formatted_meta[key] = v
        writer.add_metadata(formatted_meta)

    if password:
        writer.encrypt(password)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TestPDFParserService(unittest.TestCase):
    """Test suite covering PDFParserService requirements (Tests 1 through 10)."""

    def setUp(self):
        self.parser = PDFParserService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_single_page_pdf(self):
        """TEST 1: Single-page PDF text extraction, char_count, is_empty, and 1-indexed numbering."""
        pdf_bytes = generate_test_pdf(["Revenue for Q3 was 150 million dollars."])
        file_path = self.temp_path / "single_page.pdf"
        file_path.write_bytes(pdf_bytes)

        doc_id = str(uuid.uuid4())
        parsed = self.parser.extract_text_and_metadata(file_path=file_path, document_id=doc_id)

        self.assertIsInstance(parsed, ParsedDocument)
        self.assertEqual(parsed.document_id, doc_id)
        self.assertEqual(parsed.filename, "single_page.pdf")
        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(len(parsed.pages), 1)

        page1 = parsed.pages[0]
        self.assertIsInstance(page1, ParsedPage)
        self.assertEqual(page1.page_number, 1)
        self.assertEqual(page1.text, "Revenue for Q3 was 150 million dollars.")
        self.assertEqual(page1.char_count, len(page1.text))
        self.assertFalse(page1.is_empty)

    def test_02_multi_page_pdf(self):
        """TEST 2: Multi-page PDF produces matching total_pages and correct page count."""
        pages = [
            "Executive Summary",
            "Financial Statement",
            "Risk Factors and Disclosures",
        ]
        pdf_bytes = generate_test_pdf(pages)
        file_path = self.temp_path / "multi_page.pdf"
        file_path.write_bytes(pdf_bytes)

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.total_pages, 3)
        self.assertEqual(len(parsed.pages), 3)
        self.assertEqual([p.page_number for p in parsed.pages], [1, 2, 3])
        self.assertEqual(parsed.pages[0].text, "Executive Summary")
        self.assertEqual(parsed.pages[1].text, "Financial Statement")
        self.assertEqual(parsed.pages[2].text, "Risk Factors and Disclosures")

    def test_03_page_ordering(self):
        """TEST 3: Verify pages and their contents remain in exact sequential order."""
        pages = ["Page A Content", "Page B Content", "Page C Content"]
        pdf_bytes = generate_test_pdf(pages)
        file_path = self.temp_path / "ordering.pdf"
        file_path.write_bytes(pdf_bytes)

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.pages[0].text, "Page A Content")
        self.assertEqual(parsed.pages[1].text, "Page B Content")
        self.assertEqual(parsed.pages[2].text, "Page C Content")

    def test_04_blank_page_handling(self):
        """TEST 4: Verify blank/empty pages are preserved without dropping boundaries."""
        pages = ["Page 1 text", "", "Page 3 text"]  # Page 2 has 0 text
        pdf_bytes = generate_test_pdf(pages)
        file_path = self.temp_path / "blank_page.pdf"
        file_path.write_bytes(pdf_bytes)

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.total_pages, 3)
        self.assertEqual(len(parsed.pages), 3)

        page2 = parsed.pages[1]
        self.assertEqual(page2.page_number, 2)
        self.assertEqual(page2.text, "")
        self.assertEqual(page2.char_count, 0)
        self.assertTrue(page2.is_empty)

    def test_05_metadata_present(self):
        """TEST 5: Document metadata is extracted when present in the PDF catalog."""
        metadata = {
            "Title": "Annual Financial Report 2025",
            "Author": "Corporate Treasury",
            "Creator": "FinSight PDF Generator",
        }
        pdf_bytes = generate_test_pdf(["Sample report content"], metadata=metadata)
        file_path = self.temp_path / "meta.pdf"
        file_path.write_bytes(pdf_bytes)

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertIn("title", parsed.metadata)
        self.assertEqual(parsed.metadata["title"], "Annual Financial Report 2025")
        self.assertEqual(parsed.metadata.get("author"), "Corporate Treasury")
        self.assertEqual(parsed.metadata.get("creator"), "FinSight PDF Generator")

    def test_06_metadata_absent(self):
        """TEST 6: Document without metadata succeeds gracefully with an empty metadata dict."""
        pdf_bytes = generate_test_pdf(["Clean document"])
        file_path = self.temp_path / "no_meta.pdf"
        file_path.write_bytes(pdf_bytes)

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertIsInstance(parsed.metadata, dict)
        self.assertNotIn("title", parsed.metadata)

    def test_07_malformed_pdf(self):
        """TEST 7: Malformed/corrupt PDF raises FinSight ProcessingError without leaking internals."""
        file_path = self.temp_path / "corrupt.pdf"
        file_path.write_bytes(b"%PDF-1.7\nCorrupted binary data that is not a valid PDF")

        with self.assertRaises(ProcessingError) as ctx:
            self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertIn("Malformed or unreadable PDF document", ctx.exception.message)

    def test_08_missing_file(self):
        """TEST 8: Missing file raises FinSight ProcessingError cleanly."""
        missing_path = self.temp_path / "does_not_exist.pdf"

        with self.assertRaises(ProcessingError) as ctx:
            self.parser.extract_text_and_metadata(file_path=missing_path)

        self.assertIn("PDF file not found on storage disk", ctx.exception.message)

    def test_09_encrypted_pdf(self):
        """TEST 9: Encrypted/password-protected PDF raises ProcessingError with clear message."""
        pdf_bytes = generate_test_pdf(["Confidential financial data"], password="SecretPassword123")
        file_path = self.temp_path / "encrypted.pdf"
        file_path.write_bytes(pdf_bytes)

        with self.assertRaises(ProcessingError) as ctx:
            self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertTrue(
            "encrypted" in ctx.exception.message.lower() or "password" in ctx.exception.message.lower()
        )

    def test_10_text_normalization(self):
        """TEST 10: Verify conservative text normalization rules."""
        raw = "Line 1\r\n\r\n\r\n\r\nLine 2\twith\ttabs\n\n\nLine 3"
        normalized = self.parser.normalize_text(raw)
        self.assertEqual(normalized, "Line 1\n\nLine 2 with tabs\n\nLine 3")


class TestIdempotencyAndTaskFlow(unittest.TestCase):
    """Test suite covering task orchestration, status transitions, and idempotency."""

    def test_idempotency_skip_non_pending(self):
        """Verify process_document skips execution if status is already 'parsed', 'processing', or 'failed'."""
        for existing_status in ("parsed", "processing", "failed"):
            async def run(status_val):
                ctx = {"job_id": f"job-test-{status_val}"}
                doc_id = uuid.uuid4()

                mock_doc = MagicMock(spec=Document)
                mock_doc.id = doc_id
                mock_doc.status = status_val
                mock_doc.filename = "report.pdf"

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_doc

                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_result)

                with patch("app.tasks.definitions.async_session") as mock_session_ctx:
                    mock_session_ctx.return_value.__aenter__.return_value = mock_session
                    res = await process_document(ctx, str(doc_id))

                self.assertEqual(res["status"], "skipped")
                self.assertEqual(res["current_status"], status_val)

            asyncio.run(run(existing_status))


if __name__ == "__main__":
    unittest.main()
