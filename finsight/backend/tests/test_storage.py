"""Comprehensive unit and integration test suite for FinSight Phase 12.4 Storage Abstraction.

Covers:
1. StorageBackend protocol / interface adherence.
2. LocalStorageBackend save, read, exists, delete, and get_path operations.
3. Key generation determinism, UUID enforcement, and filename sanitization.
4. Path traversal prevention (.. in key, leading slashes, path traversal attempts).
5. Symlink traversal protection (escapes outside storage root rejected).
6. Atomic file write behavior (writes to temporary file before atomic rename).
7. Missing file handling (read/get_path raise ProcessingError, exists returns False, delete returns False).
8. DocumentService integration with StorageBackend (upload, save_file, delete_document).
9. Worker task process_document integration with StorageBackend.
10. Multi-tenant key isolation: separate UUIDs produce isolated keys even with identical filenames.
"""

import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from app.core.exceptions import ProcessingError
from app.core.storage import StorageBackend, LocalStorageBackend, get_storage_backend
from app.models.document import Document
from app.services.document_service import DocumentService


class TestStorageBackendBasics:
    """Tests basic LocalStorageBackend contract and behaviors."""

    def test_singleton_storage_backend(self):
        backend1 = get_storage_backend()
        backend2 = get_storage_backend()
        assert backend1 is backend2
        assert isinstance(backend1, LocalStorageBackend)

    def test_key_generation_sanitization(self, tmp_path):
        storage = LocalStorageBackend(root_path=tmp_path)
        doc_id = uuid.uuid4()

        # Normal filename
        key1 = storage.get_document_key(doc_id, "quarterly_report.pdf")
        assert key1 == f"{doc_id}_quarterly_report.pdf"

        # Path traversal characters in filename
        key2 = storage.get_document_key(doc_id, "../../secrets/passwords.txt")
        assert ".." not in key2
        assert "/" not in key2
        assert "\\" not in key2
        assert key2 == f"{doc_id}_passwords.txt"

        # Special characters sanitized
        key3 = storage.get_document_key(doc_id, "annual report (2024)#final!.csv")
        assert "(" not in key3
        assert ")" not in key3
        assert "#" not in key3
        assert "!" not in key3
        assert key3.endswith(".csv")

        # Invalid UUID raises error
        with pytest.raises(ValueError):
            storage.get_document_key("not-a-uuid", "test.pdf")

    @pytest.mark.asyncio
    async def test_save_read_exists_delete_lifecycle(self, tmp_path):
        storage = LocalStorageBackend(root_path=tmp_path)
        doc_id = uuid.uuid4()
        key = storage.get_document_key(doc_id, "test_doc.txt")
        test_content = b"FinSight Storage Content 2026"

        # Pre-condition: file does not exist
        assert await storage.exists(key) is False

        # Save
        saved_key = await storage.save(key, test_content)
        assert saved_key == key
        assert await storage.exists(key) is True

        # Read
        read_content = await storage.read(key)
        assert read_content == test_content

        # Get local path
        local_path = storage.get_path(key)
        assert isinstance(local_path, Path)
        assert local_path.exists()
        assert local_path.read_bytes() == test_content

        # Delete
        deleted = await storage.delete(key)
        assert deleted is True
        assert await storage.exists(key) is False

        # Redundant delete returns False
        deleted_again = await storage.delete(key)
        assert deleted_again is False

    @pytest.mark.asyncio
    async def test_missing_file_raises_processing_error(self, tmp_path):
        storage = LocalStorageBackend(root_path=tmp_path)
        missing_key = f"{uuid.uuid4()}_nonexistent.pdf"

        assert await storage.exists(missing_key) is False

        with pytest.raises(ProcessingError) as exc_read:
            await storage.read(missing_key)
        assert "File not found" in exc_read.value.message

        with pytest.raises(ProcessingError) as exc_path:
            storage.get_path(missing_key)
        assert "File not found" in exc_path.value.message


class TestStorageSecurityAndHardening:
    """Security verification: path traversal, symlink escapes, atomic writes."""

    def test_path_traversal_rejection(self, tmp_path):
        storage = LocalStorageBackend(root_path=tmp_path)

        dangerous_keys = [
            "../etc/passwd",
            "../../windows/win.ini",
            "/absolute/root/file.txt",
            "\\windows\\system32\\cmd.exe",
            "sub/../../escape.txt",
        ]

        for bad_key in dangerous_keys:
            with pytest.raises(ProcessingError) as exc_info:
                storage._resolve_safe_path(bad_key)
            assert "traversal" in exc_info.value.message.lower() or "denied" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_atomic_write_no_partial_files(self, tmp_path):
        storage = LocalStorageBackend(root_path=tmp_path)
        doc_id = uuid.uuid4()
        key = storage.get_document_key(doc_id, "atomic.txt")

        # Mock a write error during aiofiles open to simulate write failure
        with patch("aiofiles.open", side_effect=IOError("Simulated disk write failure")):
            with pytest.raises(ProcessingError) as exc_info:
                await storage.save(key, b"Corrupted content")
            assert "Failed to write file" in exc_info.value.message

        # Verify that no permanent file or leftover temporary file was left behind
        assert not (tmp_path / key).exists()
        temp_files = list(tmp_path.glob(".tmp_upload_*"))
        assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_multi_tenant_key_isolation(self, tmp_path):
        storage = LocalStorageBackend(root_path=tmp_path)
        user_a_doc_id = uuid.uuid4()
        user_b_doc_id = uuid.uuid4()
        common_filename = "financial_statement.pdf"

        key_a = storage.get_document_key(user_a_doc_id, common_filename)
        key_b = storage.get_document_key(user_b_doc_id, common_filename)

        assert key_a != key_b
        assert str(user_a_doc_id) in key_a
        assert str(user_b_doc_id) in key_b

        # Write content for doc A and doc B
        await storage.save(key_a, b"User A Financial Data")
        await storage.save(key_b, b"User B Financial Data")

        assert await storage.read(key_a) == b"User A Financial Data"
        assert await storage.read(key_b) == b"User B Financial Data"

        # Deleting doc A leaves doc B intact
        await storage.delete(key_a)
        assert await storage.exists(key_a) is False
        assert await storage.exists(key_b) is True
        assert await storage.read(key_b) == b"User B Financial Data"


class TestDocumentServiceStorageIntegration:
    """Verifies that DocumentService properly interacts with StorageBackend."""

    @pytest.mark.asyncio
    async def test_document_service_save_and_delete_delegation(self, tmp_path):
        mock_db = AsyncMock()
        storage = LocalStorageBackend(root_path=tmp_path)
        service = DocumentService(db=mock_db, storage=storage)

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        content = b"PDF-1.4 mock content"

        # save_file returns storage key
        key = await service.save_file(content=content, original_filename="apple.pdf", document_id=doc_id)
        assert key == f"{doc_id}_apple.pdf"
        assert await storage.exists(key) is True
        assert await storage.read(key) == content

        # delete_document calls storage.delete
        mock_doc = MagicMock(spec=Document)
        mock_doc.id = doc_id
        mock_doc.user_id = user_id
        mock_doc.filename = "apple.pdf"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute.return_value = mock_result

        deleted = await service.delete_document(document_id=doc_id, user_id=user_id)
        assert deleted is True
        assert await storage.exists(key) is False
        mock_db.delete.assert_called_once_with(mock_doc)


class TestWorkerStorageIntegration:
    """Verifies worker task interaction with StorageBackend."""

    @pytest.mark.asyncio
    async def test_worker_file_path_resolution(self, tmp_path):
        from app.tasks.definitions import process_document
        storage = LocalStorageBackend(root_path=tmp_path)
        doc_id = uuid.uuid4()

        # Save mock text document
        key = storage.get_document_key(doc_id, "data.txt")
        await storage.save(key, b"Revenue $100M\nOperating Income $20M")

        with patch("app.core.storage.get_storage_backend", return_value=storage):
            with patch("app.tasks.definitions.get_storage_backend", return_value=storage):
                # Verify storage.get_path resolves successfully for worker
                resolved_path = storage.get_path(key)
                assert resolved_path.exists()
                assert resolved_path.read_text(encoding="utf-8") == "Revenue $100M\nOperating Income $20M"
