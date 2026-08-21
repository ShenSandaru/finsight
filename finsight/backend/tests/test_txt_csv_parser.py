"""Comprehensive unit tests for Sprint 3.2: TextParserService, CSVParserService, Boilerplate Filtering, and PDF Regressions."""

import io
import unittest
import uuid
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject

from app.core.exceptions import ProcessingError
from app.services.pdf_parser import PDFParserService, ParsedPage, ParsedDocument
from app.services.text_parser import TextParserService
from app.services.csv_parser import CSVParserService
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


class TestTextParserService(unittest.TestCase):
    """Test suite covering TextParserService (TXT 1 to 7)."""

    def setUp(self):
        self.parser = TextParserService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_txt_01_utf8_text(self):
        """TXT 1: Standard UTF-8 plain text parsing and single logical page representation."""
        file_path = self.temp_path / "sample.txt"
        file_path.write_text("Hello FinSight Analyst.\nRevenue is steady.", encoding="utf-8")

        parsed = self.parser.extract_text_and_metadata(file_path=file_path, document_id="txt-01")

        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(len(parsed.pages), 1)
        self.assertEqual(parsed.metadata["format"], "txt")
        self.assertEqual(parsed.metadata["encoding"], "utf-8")
        self.assertIn("Revenue is steady.", parsed.pages[0].text)
        self.assertEqual(parsed.pages[0].page_number, 1)
        self.assertFalse(parsed.pages[0].is_empty)

    def test_txt_02_utf8_bom(self):
        """TXT 2: UTF-8 with Byte Order Mark (BOM) decoded cleanly."""
        file_path = self.temp_path / "bom.txt"
        file_path.write_bytes(b"\xef\xbb\xbfFinancial disclosure statement with BOM.")

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(parsed.metadata["encoding"], "utf-8-sig")
        self.assertEqual(parsed.pages[0].text, "Financial disclosure statement with BOM.")

    def test_txt_03_latin1_text(self):
        """TXT 3: Latin-1 encoded text containing accented characters (e.g. Café, résumé)."""
        file_path = self.temp_path / "latin1.txt"
        file_path.write_bytes("Société Générale earnings résumé".encode("latin-1"))

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.total_pages, 1)
        self.assertIn("Société Générale", parsed.pages[0].text)

    def test_txt_04_empty_text(self):
        """TXT 4: Empty text file returns single empty logical page."""
        file_path = self.temp_path / "empty.txt"
        file_path.write_text("", encoding="utf-8")

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(parsed.pages[0].text, "")
        self.assertEqual(parsed.pages[0].char_count, 0)
        self.assertTrue(parsed.pages[0].is_empty)

    def test_txt_05_multiline_and_crlf_normalization(self):
        """TXT 5 & 6: Normalization of CRLF to LF and collapsing excessive blank lines."""
        raw = "Header\r\n\r\n\r\n\r\nParagraph 1\twith tab\r\n\r\nParagraph 2"
        file_path = self.temp_path / "crlf.txt"
        file_path.write_bytes(raw.encode("utf-8"))

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.pages[0].text, "Header\n\nParagraph 1 with tab\n\nParagraph 2")

    def test_txt_07_invalid_binary_null_bytes(self):
        """TXT 7: Binary null bytes raise ProcessingError cleanly."""
        file_path = self.temp_path / "binary.txt"
        file_path.write_bytes(b"Valid text prefix\x00\x01\x02binary junk")

        with self.assertRaises(ProcessingError) as ctx:
            self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertIn("binary null bytes", ctx.exception.message)


class TestCSVParserService(unittest.TestCase):
    """Test suite covering CSVParserService (CSV 1 to 8)."""

    def setUp(self):
        self.parser = CSVParserService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_csv_01_simple_csv(self):
        """CSV 1 & 2: Simple CSV with header and rows preserves columns and row count."""
        content = "Quarter,Revenue,NetIncome\nQ1,100,20\nQ2,120,25\nQ3,150,35\n"
        file_path = self.temp_path / "simple.csv"
        file_path.write_text(content, encoding="utf-8")

        parsed = self.parser.extract_text_and_metadata(file_path=file_path, document_id="csv-01")

        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(parsed.metadata["format"], "csv")
        self.assertEqual(parsed.metadata["column_names"], ["Quarter", "Revenue", "NetIncome"])
        self.assertEqual(parsed.metadata["column_count"], 3)
        self.assertEqual(parsed.metadata["row_count"], 4)
        self.assertIn("Q3,150,35", parsed.pages[0].text)

    def test_csv_03_quoted_values_and_commas(self):
        """CSV 3 & 4: CSV with quoted strings containing internal commas and quotes."""
        content = 'Metric,"Value, in Millions",Notes\nRevenue,"$1,250.50","Includes Q4, restated"\n'
        file_path = self.temp_path / "quoted.csv"
        file_path.write_text(content, encoding="utf-8")

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.metadata["column_names"], ["Metric", "Value, in Millions", "Notes"])
        self.assertEqual(parsed.metadata["row_count"], 2)
        self.assertEqual(parsed.pages[0].metadata["rows"][1][1], "$1,250.50")
        self.assertEqual(parsed.pages[0].metadata["rows"][1][2], "Includes Q4, restated")

    def test_csv_05_utf8_bom(self):
        """CSV 5 & 6: CSV with UTF-8 BOM encoding."""
        content = b"\xef\xbb\xbfQuarter,Revenue\nQ1,500\n"
        file_path = self.temp_path / "bom.csv"
        file_path.write_bytes(content)

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.metadata["encoding"], "utf-8-sig")
        self.assertEqual(parsed.metadata["column_names"], ["Quarter", "Revenue"])

    def test_csv_07_empty_csv(self):
        """CSV 7: Completely empty CSV returns empty logical page."""
        file_path = self.temp_path / "empty.csv"
        file_path.write_text("", encoding="utf-8")

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(parsed.metadata["row_count"], 0)
        self.assertEqual(parsed.metadata["column_count"], 0)
        self.assertTrue(parsed.pages[0].is_empty)

    def test_csv_08_binary_corrupt_csv(self):
        """CSV 8: CSV with binary null bytes raises ProcessingError cleanly."""
        file_path = self.temp_path / "corrupt.csv"
        file_path.write_bytes(b"Col1,Col2\n\x00\x00corrupt,row\n")

        with self.assertRaises(ProcessingError):
            self.parser.extract_text_and_metadata(file_path=file_path)


class TestBoilerplateFiltering(unittest.TestCase):
    """Test suite covering conservative header/footer repeated boilerplate filtering."""

    def test_boilerplate_removal_and_financial_protection(self):
        """
        Verify repeated corporate headers and 'Page X of Y' footers are filtered,
        while legitimate repeated financial numbers are strictly preserved.
        """
        pages = [
            ParsedPage(
                page_number=1,
                text="ACME Corp Annual Report\nPage 1 of 3\nRevenue $100\nTotal Assets $500\nConfidential - Internal Use",
                char_count=100,
                is_empty=False,
            ),
            ParsedPage(
                page_number=2,
                text="ACME Corp Annual Report\nPage 2 of 3\nRevenue $200\nTotal Assets $500\nConfidential - Internal Use",
                char_count=100,
                is_empty=False,
            ),
            ParsedPage(
                page_number=3,
                text="ACME Corp Annual Report\nPage 3 of 3\nRevenue $300\nTotal Assets $500\nConfidential - Internal Use",
                char_count=100,
                is_empty=False,
            ),
        ]

        filtered = PDFParserService.filter_repeated_boilerplate(pages)

        for p in filtered:
            # Header and footer boilerplate should be removed
            self.assertNotIn("ACME Corp Annual Report", p.text)
            self.assertNotIn("Confidential - Internal Use", p.text)
            self.assertNotIn("Page 1 of 3", p.text)
            self.assertNotIn("Page 2 of 3", p.text)
            self.assertNotIn("Page 3 of 3", p.text)

            # Protected financial metric repeated across pages must be retained!
            self.assertIn("Total Assets $500", p.text)

        self.assertIn("Revenue $100", filtered[0].text)
        self.assertIn("Revenue $200", filtered[1].text)
        self.assertIn("Revenue $300", filtered[2].text)


class TestPDFParserRegression(unittest.TestCase):
    """Regression test suite ensuring Sprint 3.1 PDF functionality remains 100% intact."""

    def setUp(self):
        self.parser = PDFParserService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pdf_multipage_and_metadata(self):
        """Verify multi-page PDF text extraction and catalog metadata."""
        metadata = {"Title": "Alphabet 10-Q 2025", "Author": "Google Finance"}
        pdf_bytes = generate_test_pdf(["Page 1 Content", "Page 2 Content"], metadata=metadata)
        file_path = self.temp_path / "test.pdf"
        file_path.write_bytes(pdf_bytes)

        parsed = self.parser.extract_text_and_metadata(file_path=file_path)

        self.assertEqual(parsed.total_pages, 2)
        self.assertEqual(parsed.metadata.get("title"), "Alphabet 10-Q 2025")
        self.assertEqual(parsed.pages[0].text, "Page 1 Content")
        self.assertEqual(parsed.pages[1].text, "Page 2 Content")


if __name__ == "__main__":
    unittest.main()
