"""Test fixtures generator for PDF parser testing."""

import io
from pathlib import Path
from pypdf import PdfWriter


def create_minimal_pdf_bytes(text: str, metadata: dict[str, str] | None = None) -> bytes:
    """Create a valid single-page PDF with text stream and optional metadata."""
    # Build standard PDF object structure in bytes
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)  # Standard Letter
    
    if metadata:
        writer.add_metadata(metadata)
        
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
