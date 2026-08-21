"""Comprehensive unit tests for Sprint 4.1: Financial Table Extraction Foundation."""

import io
import unittest
import uuid
import tempfile
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject

from app.core.exceptions import ProcessingError
from app.services.table_extractor import TableExtractorService, ExtractedTable


def generate_pdf_with_table(
    pages_tables: list[tuple[str, list[list[str]]]], # list of (page_text_above, table_grid)
    metadata: dict[str, str] | None = None,
) -> bytes:
    """
    Generate synthetic PDF containing real drawn vector lines (rectangles/lines) and text
    so pdfplumber's line/rect table finder can accurately detect cells.
    """
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

        # Draw page text above line by line
        if page_text:
            lines = page_text.split("\n")
            curr_y = 720
            for l in lines:
                safe_text = l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                stream_cmds.append(f"BT /F1 12 Tf 72 {curr_y} Td ({safe_text}) Tj ET")
                curr_y -= 16

        # Draw table grid if rows are present
        if table_rows:
            num_rows = len(table_rows)
            num_cols = max(len(r) for r in table_rows)
            x_start, y_start = 72, 650
            col_width = 450 / max(1, num_cols)
            row_height = 25

            # Draw horizontal and vertical grid lines for pdfplumber line detection
            stream_cmds.append("0.5 w 0 G") # line width and stroke color
            # Horizontals
            for r in range(num_rows + 1):
                y = y_start - (r * row_height)
                stream_cmds.append(f"{x_start} {y} m {x_start + (num_cols * col_width)} {y} l S")
            # Verticals
            for c in range(num_cols + 1):
                x = x_start + (c * col_width)
                stream_cmds.append(f"{x} {y_start} m {x} {y_start - (num_rows * row_height)} l S")

            # Draw cell text
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


class TestTableExtractorService(unittest.TestCase):
    """Test suite covering TableExtractorService functionality (Parts 1 to 17)."""

    def setUp(self):
        self.extractor = TableExtractorService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_simple_two_column_table(self):
        """TEST 1 & 2 & 3: Simple 2-column table detection, row and column preservation."""
        table_grid = [
            ["Fiscal Year", "Revenue"],
            ["2024", "$100M"],
            ["2025", "$150M"],
        ]
        pdf_bytes = generate_pdf_with_table([("Company Financial Overview", table_grid)])
        file_path = self.temp_path / "simple_table.pdf"
        file_path.write_bytes(pdf_bytes)

        tables = self.extractor.extract_tables_from_pdf(file_path=file_path, document_id="doc-1")

        self.assertEqual(len(tables), 1)
        tbl = tables[0]
        self.assertIsInstance(tbl, ExtractedTable)
        self.assertEqual(tbl.page_number, 1)
        self.assertEqual(tbl.column_count, 2)
        self.assertEqual(tbl.headers, ["Fiscal Year", "Revenue"])
        self.assertEqual(len(tbl.rows), 2)
        self.assertEqual(tbl.rows[0], ["2024", "$100M"])
        self.assertEqual(tbl.rows[1], ["2025", "$150M"])

    def test_02_multi_column_financial_table(self):
        """TEST 4 & 5: Multi-column financial table with headers, currencies, and negative numbers."""
        page_text = "Consolidated Statements of Operations\n(in millions)"
        table_grid = [
            ["Metric", "2023", "2024", "2025"],
            ["Revenue", "$1,000.50", "$1,200.00", "$1,450.75"],
            ["Cost of Goods", "($600.00)", "($700.00)", "($800.00)"],
            ["Operating Margin", "15.5%", "17.2%", "19.8%"],
            ["Net Income", "$250.00", "$320.00", "$410.00"],
        ]
        pdf_bytes = generate_pdf_with_table([(page_text, table_grid)])
        file_path = self.temp_path / "financial_stmt.pdf"
        file_path.write_bytes(pdf_bytes)

        tables = self.extractor.extract_tables_from_pdf(file_path=file_path, document_id="doc-2")

        self.assertEqual(len(tables), 1)
        tbl = tables[0]
        self.assertEqual(tbl.column_count, 4)
        self.assertEqual(tbl.title, "Consolidated Statements of Operations")
        self.assertEqual(tbl.units, "millions")
        self.assertEqual(tbl.currency, "USD")
        self.assertEqual(tbl.headers, ["Metric", "2023", "2024", "2025"])
        self.assertEqual(len(tbl.rows), 4)

        # Check negative parentheses preserved
        cost_row = tbl.rows[1]
        self.assertEqual(cost_row[0], "Cost of Goods")
        self.assertIn("($600.00)", cost_row[1])

        # Check percentage preserved
        margin_row = tbl.rows[2]
        self.assertEqual(margin_row[0], "Operating Margin")
        self.assertEqual(margin_row[1], "15.5%")

    def test_03_sparse_empty_cells(self):
        """TEST 6: Table with empty cells normalizes empty cells to empty strings without crashing."""
        table_grid = [
            ["Item", "Q1", "Q2", "Q3"],
            ["Software", "$50M", "", "$60M"],
            ["Services", "", "$20M", ""],
        ]
        pdf_bytes = generate_pdf_with_table([("Quarterly Segment Breakdown", table_grid)])
        file_path = self.temp_path / "sparse.pdf"
        file_path.write_bytes(pdf_bytes)

        tables = self.extractor.extract_tables_from_pdf(file_path=file_path)

        self.assertEqual(len(tables), 1)
        tbl = tables[0]
        self.assertEqual(tbl.rows[0], ["Software", "$50M", "", "$60M"])
        self.assertEqual(tbl.rows[1], ["Services", "", "$20M", ""])

    def test_04_markdown_generation(self):
        """TEST 11: Markdown generation creates clean, valid markdown table syntax."""
        headers = ["Asset Class", "Allocation", "Return"]
        rows = [
            ["Equities", "60%", "12.4%"],
            ["Fixed Income", "40%", "4.2%"],
        ]
        md = TableExtractorService.generate_markdown(headers, rows)
        expected = (
            "| Asset Class | Allocation | Return |\n"
            "| --- | --- | --- |\n"
            "| Equities | 60% | 12.4% |\n"
            "| Fixed Income | 40% | 4.2% |"
        )
        self.assertEqual(md, expected)

    def test_05_no_table_pdf(self):
        """TEST 12: PDF with no tables returns empty list without error."""
        pdf_bytes = generate_pdf_with_table([("Standard narrative prose without any table grid.", [])])
        file_path = self.temp_path / "no_table.pdf"
        file_path.write_bytes(pdf_bytes)

        tables = self.extractor.extract_tables_from_pdf(file_path=file_path)
        self.assertEqual(tables, [])

    def test_06_multipage_pdf_tables(self):
        """TEST 13: Multi-page PDF with tables on distinct pages correctly retains source page numbers."""
        page1_grid = [["Product", "Units"], ["Alpha", "1000"]]
        page2_grid = [["Region", "Sales"], ["EMEA", "$500k"]]

        pdf_bytes = generate_pdf_with_table([
            ("Balance Sheet Overview", page1_grid),
            ("Geographic Breakdown", page2_grid),
        ])
        file_path = self.temp_path / "multipage_tables.pdf"
        file_path.write_bytes(pdf_bytes)

        tables = self.extractor.extract_tables_from_pdf(file_path=file_path)

        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0].page_number, 1)
        self.assertEqual(tables[0].headers, ["Product", "Units"])
        self.assertEqual(tables[1].page_number, 2)
        self.assertEqual(tables[1].headers, ["Region", "Sales"])

    def test_07_malformed_pdf_handling(self):
        """TEST 14: Malformed PDF raises ProcessingError cleanly."""
        file_path = self.temp_path / "corrupt.pdf"
        file_path.write_bytes(b"%PDF-1.7\nCorrupted binary table data")

        with self.assertRaises(ProcessingError) as ctx:
            self.extractor.extract_tables_from_pdf(file_path=file_path)

        self.assertIn("Malformed or unreadable PDF", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
