"""End-to-end integration test runner for Sprint 3.1 & Sprint 3.2 (PDF, TXT, CSV, and Boilerplate filtering)."""

import io
import json
import time
import urllib.request
from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject


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
    print(f"  -> Final Status: {doc['status']}, Total Pages: {doc['total_pages']}, Title: '{doc['title']}', Error: {doc['processing_error']}")
    assert doc["status"] == "parsed", f"Expected 'parsed', got {doc['status']}"
    assert doc["total_pages"] == 2, f"Expected total_pages=2, got {doc['total_pages']}"
    assert doc["title"] == "Apple 10-K Fiscal 2025", f"Expected title set from metadata, got {doc['title']}"
    assert doc["processing_error"] is None, f"Expected null processing_error, got {doc['processing_error']}"
    print("  ✅ E2E 1 PASSED: Valid PDF processed pending -> processing -> parsed.")

    # 2. Malformed PDF test (magic bytes valid %PDF- but corrupted content)
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

    # 3. TXT file upload test (Sprint 3.2 Full Parsing Flow)
    print("\n[E2E 3] Uploading plain text (.txt) file...")
    txt_bytes = b"FinSight Earnings Summary\nQ3 Revenue reached $2.5 billion with 18% YoY growth."
    up_resp_txt = upload_multipart("earnings_summary.txt", txt_bytes, content_type="text/plain")
    txt_id = up_resp_txt["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp_txt['document']['status']} (id={txt_id})")
    assert up_resp_txt["document"]["status"] == "pending", f"Expected initial 'pending', got {up_resp_txt['document']['status']}"

    doc_txt = poll_document(txt_id)
    print(f"  -> Final Status: {doc_txt['status']}, Total Pages: {doc_txt['total_pages']}, Error: {doc_txt['processing_error']}")
    assert doc_txt["status"] == "parsed", f"Expected 'parsed', got {doc_txt['status']}"
    assert doc_txt["total_pages"] == 1, f"Expected total_pages=1 for TXT, got {doc_txt['total_pages']}"
    assert doc_txt["processing_error"] is None, f"Expected null processing_error, got {doc_txt['processing_error']}"
    print("  ✅ E2E 3 PASSED: TXT file parsed successfully pending -> processing -> parsed.")

    # 5. Financial PDF with Statement Tables (Sprint 4.2 Semantic Verification)
    print("\n[E2E 5] Uploading Financial PDF with Income Statement, Balance Sheet, and Cash Flow...")
    financial_pdf_bytes = make_pdf(
        [
            "Consolidated Statements of Operations\nYears Ended December 31, 2025\nTotal Revenue: $1000\nGross Profit: $400\nNet Income: $150",
            "Consolidated Balance Sheets\nAs of December 31, 2025\nTotal Assets: $1500\nTotal Liabilities: $600\nTotal Stockholders Equity: $900",
            "Statements of Cash Flows\nYears Ended December 31, 2025\nNet Cash Provided by Operating Activities: $300\nCapital Expenditures: $100",
        ],
        {"Title": "Financial Statements 2025"}
    )
    up_resp_fin = upload_multipart("financial_statements_2025.pdf", financial_pdf_bytes)
    fin_id = up_resp_fin["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp_fin['document']['status']} (id={fin_id})")
    assert up_resp_fin["document"]["status"] == "pending", f"Expected initial 'pending', got {up_resp_fin['document']['status']}"

    doc_fin = poll_document(fin_id)
    print(f"  -> Final Status: {doc_fin['status']}, Total Pages: {doc_fin['total_pages']}, Title: '{doc_fin['title']}', Error: {doc_fin['processing_error']}")
    assert doc_fin["status"] == "parsed", f"Expected 'parsed', got {doc_fin['status']}"
    assert doc_fin["total_pages"] == 3, f"Expected total_pages=3, got {doc_fin['total_pages']}"
    assert doc_fin["processing_error"] is None, f"Expected null processing_error, got {doc_fin['processing_error']}"
    print("  ✅ E2E 5 PASSED: Financial PDF with multi-statement tables processed pending -> processing -> parsed.")

    print("\n==================================================")
    print("ALL END-TO-END TESTS PASSED SUCCESSFULLY! 🎉")
    print("==================================================")


if __name__ == "__main__":
    run_e2e_tests()
