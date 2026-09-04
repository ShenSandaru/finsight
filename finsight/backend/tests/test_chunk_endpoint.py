"""Tests for DocumentChunk endpoint and service retrieval (Phase 11.5)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.exceptions import ChunkNotFoundError
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.document import DocumentChunkResponse
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_get_chunk_service_found():
    mock_db = AsyncMock()
    service = DocumentService(mock_db)

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.title = "Apple Inc. Form 10-K"
    mock_doc.filename = "apple_10k.pdf"

    mock_chunk = MagicMock(spec=Chunk)
    mock_chunk.id = chunk_id
    mock_chunk.document_id = doc_id
    mock_chunk.content = "Revenue was $412B in FY2025."
    mock_chunk.chunk_type = "text"
    mock_chunk.chunk_index = 3
    mock_chunk.page_number = 15
    mock_chunk.metadata_ = {"section": "Item 7"}
    mock_chunk.created_at = datetime.utcnow()
    mock_chunk.document = mock_doc

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_chunk
    mock_db.execute.return_value = mock_result

    retrieved = await service.get_chunk(chunk_id)

    assert retrieved is not None
    assert retrieved.id == chunk_id
    assert retrieved.content == "Revenue was $412B in FY2025."
    assert retrieved.document.title == "Apple Inc. Form 10-K"


@pytest.mark.asyncio
async def test_get_chunk_service_not_found():
    mock_db = AsyncMock()
    service = DocumentService(mock_db)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    chunk_id = uuid.uuid4()
    retrieved = await service.get_chunk(chunk_id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_get_chunk_api_endpoint_success():
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    now = datetime.utcnow()

    mock_doc = MagicMock(spec=Document)
    mock_doc.title = "Microsoft Corporation 10-Q"
    mock_doc.filename = "msft_10q.pdf"

    mock_chunk = MagicMock(spec=Chunk)
    mock_chunk.id = chunk_id
    mock_chunk.document_id = doc_id
    mock_chunk.content = "| Period | Revenue |\n| Q1 | $65.6B |"
    mock_chunk.chunk_type = "table"
    mock_chunk.chunk_index = 7
    mock_chunk.page_number = 22
    mock_chunk.metadata_ = {"table_title": "Condensed Consolidated Statements of Income"}
    mock_chunk.created_at = now
    mock_chunk.document = mock_doc

    with patch.object(DocumentService, "get_chunk", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_chunk

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/documents/chunks/{chunk_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(chunk_id)
            assert data["document_id"] == str(doc_id)
            assert data["document_title"] == "Microsoft Corporation 10-Q"
            assert data["document_filename"] == "msft_10q.pdf"
            assert data["content"] == "| Period | Revenue |\n| Q1 | $65.6B |"
            assert data["chunk_type"] == "table"
            assert data["page_number"] == 22
            assert data["metadata"]["table_title"] == "Condensed Consolidated Statements of Income"


@pytest.mark.asyncio
async def test_get_chunk_api_endpoint_not_found():
    chunk_id = uuid.uuid4()

    with patch.object(DocumentService, "get_chunk", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/documents/chunks/{chunk_id}")

            assert response.status_code == 404
            data = response.json()
            assert data["error"]["code"] == "NOT_FOUND"
            assert str(chunk_id) in data["error"]["message"]


@pytest.mark.asyncio
async def test_get_chunk_api_endpoint_invalid_uuid():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/documents/chunks/invalid-uuid-string")
        assert response.status_code == 422
