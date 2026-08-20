"""End-to-end integration test runner for Sprint 3.1."""

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

    # 3. TXT file upload test
    print("\n[E2E 3] Uploading TXT file (controlled unsupported behavior)...")
    txt_bytes = b"Sample financial statement text content."
    up_resp_txt = upload_multipart("statement.txt", txt_bytes, content_type="text/plain")
    txt_id = up_resp_txt["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp_txt['document']['status']} (id={txt_id})")

    doc_txt = poll_document(txt_id)
    print(f"  -> Final Status: {doc_txt['status']}, Processing Error: '{doc_txt['processing_error']}'")
    assert doc_txt["status"] == "failed", f"Expected 'failed', got {doc_txt['status']}"
    assert "TXT parsing is not implemented yet" in (doc_txt["processing_error"] or ""), f"Unexpected error: {doc_txt['processing_error']}"
    print("  ✅ E2E 3 PASSED: TXT file handled with controlled failure status.")

    # 4. CSV file upload test
    print("\n[E2E 4] Uploading CSV file (controlled unsupported behavior)...")
    csv_bytes = b"Quarter,Revenue,NetIncome\nQ1,100,20\nQ2,120,25\n"
    up_resp_csv = upload_multipart("metrics.csv", csv_bytes, content_type="text/csv")
    csv_id = up_resp_csv["document"]["id"]
    print(f"  -> Uploaded successfully. Initial status: {up_resp_csv['document']['status']} (id={csv_id})")

    doc_csv = poll_document(csv_id)
    print(f"  -> Final Status: {doc_csv['status']}, Processing Error: '{doc_csv['processing_error']}'")
    assert doc_csv["status"] == "failed", f"Expected 'failed', got {doc_csv['status']}"
    assert "CSV parsing is not implemented yet" in (doc_csv["processing_error"] or ""), f"Unexpected error: {doc_csv['processing_error']}"
    print("  ✅ E2E 4 PASSED: CSV file handled with controlled failure status.")

    print("\n==================================================")
    print("ALL END-TO-END TESTS PASSED SUCCESSFULLY! 🎉")
    print("==================================================")


if __name__ == "__main__":
    run_e2e_tests()
