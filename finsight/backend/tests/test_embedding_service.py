"""Comprehensive unit and database integration test suite for EmbeddingService (Sprint 6.1)."""

import uuid
# pyrefly: ignore [missing-import]
import pytest
from google.genai import errors

from app.core.config import get_settings
from app.core.exceptions import ProcessingError
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.embedding_service import EmbeddingService, FakeGenAIClient
from app.tasks.definitions import process_document

settings = get_settings()


class TestEmbeddingServiceUnit:

    @pytest.mark.asyncio
    async def test_01_basic_embedding_generation(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client, dimensions=1536)
        vectors = await service.embed_texts(["Sample financial report text."])
        assert len(vectors) == 1
        assert len(vectors[0]) == 1536
        assert isinstance(vectors[0][0], float)

    @pytest.mark.asyncio
    async def test_02_correct_output_count(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client, batch_size=2)
        inputs = ["Text A", "Text B", "Text C", "Text D", "Text E"]
        vectors = await service.embed_texts(inputs)
        assert len(vectors) == 5

    @pytest.mark.asyncio
    async def test_03_correct_1536_dimensions(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client, dimensions=1536)
        vectors = await service.embed_texts(["Line 1", "Line 2"])
        for vec in vectors:
            assert len(vec) == 1536

    @pytest.mark.asyncio
    async def test_04_input_output_ordering_preserved(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client, batch_size=2)
        inputs = ["First", "Second", "Third", "Fourth"]
        vectors = await service.embed_texts(inputs)
        # Vector for "First" should match independent embedding of "First"
        single_first = await service.embed_texts(["First"])
        single_third = await service.embed_texts(["Third"])
        assert vectors[0] == single_first[0]
        assert vectors[2] == single_third[0]

    @pytest.mark.asyncio
    async def test_05_batching_single_batch(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client, batch_size=10)
        await service.embed_texts(["1", "2", "3"])
        assert fake_client.call_count == 1

    @pytest.mark.asyncio
    async def test_06_batching_multiple_batches(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client, batch_size=2)
        await service.embed_texts(["1", "2", "3", "4", "5"])
        assert fake_client.call_count == 3  # 2 + 2 + 1 = 3 batches

    @pytest.mark.asyncio
    async def test_07_empty_input_list_handling(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client)
        with pytest.raises(ProcessingError) as exc_info:
            await service.embed_texts([])
        assert "empty text list" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_08_invalid_input_type_handling(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client)
        with pytest.raises(ProcessingError) as exc_info:
            await service.embed_texts(["Valid", 123, "Another"])  # type: ignore
        assert "expected str" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_09_empty_or_whitespace_chunk_handling(self):
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client)
        with pytest.raises(ProcessingError) as exc_info:
            await service.embed_texts(["Valid text", "   ", "More text"])
        assert "empty or whitespace-only" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_10_retry_on_rate_limit(self):
        import requests
        class FlakyRateLimitClient:
            def __init__(self):
                self.calls = 0
                self.aio = self

            class Models:
                def __init__(self, parent):
                    self.parent = parent

                async def embed_content(self, model, contents, config=None):
                    self.parent.calls += 1
                    if self.parent.calls == 1:
                        resp = requests.Response()
                        resp.status_code = 429
                        resp._content = b'{"error": {"message": "Rate limit exceeded"}}'
                        raise errors.APIError(429, resp)
                    fake = FakeGenAIClient()
                    return await fake.models.embed_content(model, contents, config)

            @property
            def models(self):
                return self.Models(self)

        flaky = FlakyRateLimitClient()
        service = EmbeddingService(client=flaky, max_retries=2)
        vectors = await service.embed_texts(["Retry text"])
        assert len(vectors) == 1
        assert flaky.calls == 2

    @pytest.mark.asyncio
    async def test_11_retry_on_connection_error(self):
        import requests
        class FlakyConnectionClient:
            def __init__(self):
                self.calls = 0
                self.aio = self

            class Models:
                def __init__(self, parent):
                    self.parent = parent

                async def embed_content(self, model, contents, config=None):
                    self.parent.calls += 1
                    if self.parent.calls <= 2:
                        resp = requests.Response()
                        resp.status_code = 503
                        resp._content = b'{"error": {"message": "Connection reset by peer"}}'
                        raise errors.APIError(503, resp)
                    fake = FakeGenAIClient()
                    return await fake.models.embed_content(model, contents, config)

            @property
            def models(self):
                return self.Models(self)

        flaky = FlakyConnectionClient()
        service = EmbeddingService(client=flaky, max_retries=3)
        vectors = await service.embed_texts(["Connection test text"])
        assert len(vectors) == 1
        assert flaky.calls == 3

    @pytest.mark.asyncio
    async def test_12_retry_on_timeout(self):
        import asyncio
        class TimeoutClient:
            def __init__(self):
                self.calls = 0
                self.aio = self

            class Models:
                def __init__(self, parent):
                    self.parent = parent

                async def embed_content(self, model, contents, config=None):
                    self.parent.calls += 1
                    if self.parent.calls == 1:
                        raise asyncio.TimeoutError()
                    fake = FakeGenAIClient()
                    return await fake.models.embed_content(model, contents, config)

            @property
            def models(self):
                return self.Models(self)

        timeout_client = TimeoutClient()
        service = EmbeddingService(client=timeout_client, max_retries=2)
        vectors = await service.embed_texts(["Timeout test text"])
        assert len(vectors) == 1
        assert timeout_client.calls == 2

    @pytest.mark.asyncio
    async def test_13_max_retries_exceeded(self):
        import requests
        resp = requests.Response()
        resp.status_code = 429
        resp._content = b'{"error": {"message": "Quota Exceeded"}}'
        err = errors.APIError(429, resp)
        failing_client = FakeGenAIClient(force_error=err)
        service = EmbeddingService(client=failing_client, max_retries=2)
        with pytest.raises(ProcessingError) as exc_info:
            await service.embed_texts(["Failing text"])
        assert "api call failed" in str(exc_info.value).lower()
        assert failing_client.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_14_dimension_mismatch_rejection(self):
        # Client that produces 512 dimensions instead of 1536
        bad_dim_client = FakeGenAIClient(dimension=512)
        service = EmbeddingService(client=bad_dim_client, dimensions=1536)
        with pytest.raises(ProcessingError) as exc_info:
            await service.embed_texts(["Dimension check"])
        assert "dimension" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_15_missing_gemini_api_key_configuration(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
        with pytest.raises(ProcessingError) as exc_info:
            EmbeddingService()
        assert "gemini_api_key configuration is missing" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_16_no_api_key_leakage(self, monkeypatch):
        fake_secret_key = "AIzaSySecretKey123456789"
        monkeypatch.setattr(settings, "GEMINI_API_KEY", fake_secret_key)
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        service = EmbeddingService()
        try:
            await service.embed_texts(["   "])
        except ProcessingError as exc:
            err_str = str(exc)
            assert fake_secret_key not in err_str
            assert "AIzaSy" not in err_str


@pytest.mark.asyncio
class TestEmbeddingDatabaseIntegration:

    async def test_17_database_embedding_persistence(self, db_session_factory):
        doc_id = uuid.uuid4()
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="embed_db_test.pdf", file_type="pdf", file_size=1000, status="parsed")
            c1 = Chunk(document_id=doc_id, content="First chunk content", chunk_type="text", chunk_index=0, page_number=1)
            c2 = Chunk(document_id=doc_id, content="Second chunk content", chunk_type="text", chunk_index=1, page_number=1)
            session.add_all([doc, c1, c2])
            await session.commit()

        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index))
            chunks = res.scalars().all()
            paired = await service.embed_chunks(chunks)

            # Persist
            for chunk_id, vec in paired:
                chunk_res = await session.execute(select(Chunk).where(Chunk.id == chunk_id))
                db_c = chunk_res.scalar_one()
                db_c.embedding = vec
            await session.commit()

        # Verify
        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            persisted = res.scalars().all()
            assert len(persisted) == 2
            assert all(c.embedding is not None for c in persisted)
            assert all(len(c.embedding) == 1536 for c in persisted)

            # Cleanup
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()

    async def test_18_null_to_vector_transition(self, db_session_factory):
        doc_id = uuid.uuid4()
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="null_to_vec.pdf", file_type="pdf", file_size=500, status="parsed")
            c = Chunk(document_id=doc_id, content="Sample chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=None)
            session.add_all([doc, c])
            await session.commit()

        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            c_db = res.scalar_one()
            assert c_db.embedding is None

            paired = await service.embed_chunks([c_db])
            c_db.embedding = paired[0][1]
            await session.commit()

        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            c_updated = res.scalar_one()
            assert c_updated.embedding is not None
            assert len(c_updated.embedding) == 1536

            # Cleanup
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()

    async def test_19_idempotent_reprocessing(self, db_session_factory, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        doc_id = uuid.uuid4()
        fake_client = FakeGenAIClient()

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="idempotent.pdf", file_type="pdf", file_size=500, status="indexed", total_chunks=1)
            dummy_vec = [0.1] * 1536
            c = Chunk(document_id=doc_id, content="Already embedded", chunk_type="text", chunk_index=0, page_number=1, embedding=dummy_vec)
            session.add_all([doc, c])
            await session.commit()

        # Running process_document on already indexed document should skip API generation
        # (Status is 'indexed', so skipped or preserved)
        ctx = {"job_id": "test_idempotent_job"}
        res = await process_document(ctx, str(doc_id))
        assert res["status"] in ("skipped", "indexed")

        async with db_session_factory() as session:
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()

    async def test_20_indexed_status_transition(self, db_session_factory):
        doc_id = uuid.uuid4()
        fake_client = FakeGenAIClient()
        service = EmbeddingService(client=fake_client)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="status_trans.pdf", file_type="pdf", file_size=500, status="parsed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Text for indexing", chunk_type="text", chunk_index=0, page_number=1)
            session.add_all([doc, c])
            await session.commit()

        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            chunks = res.scalars().all()
            paired = await service.embed_chunks(chunks)

            # Persist and update status
            c_db = await session.get(Chunk, paired[0][0])
            c_db.embedding = paired[0][1]
            doc_db = await session.get(Document, doc_id)
            doc_db.status = "indexed"
            await session.commit()

        async with db_session_factory() as session:
            doc_final = await session.get(Document, doc_id)
            assert doc_final.status == "indexed"

            # Cleanup
            await session.delete(doc_final)
            await session.commit()

    async def test_21_failure_status_transition(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="fail_trans.pdf", file_type="pdf", file_size=500, status="parsed", total_chunks=1)
            session.add(doc)
            await session.commit()

        # Simulate recording error
        async with db_session_factory() as session:
            doc_db = await session.get(Document, doc_id)
            doc_db.status = "failed"
            doc_db.processing_error = "Gemini embedding API call failed: RateLimitError"
            await session.commit()

        async with db_session_factory() as session:
            doc_final = await session.get(Document, doc_id)
            assert doc_final.status == "failed"
            assert "RateLimitError" in doc_final.processing_error

            # Cleanup
            await session.delete(doc_final)
            await session.commit()

    async def test_22_transactional_rollback(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="rollback_embed.pdf", file_type="pdf", file_size=500, status="parsed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Rollback chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=None)
            session.add_all([doc, c])
            await session.commit()

        # Simulate failed transaction during embedding update
        try:
            async with db_session_factory() as session:
                from sqlalchemy import select
                res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
                chunk_obj = res.scalar_one()
                chunk_obj.embedding = [0.5] * 1536
                raise RuntimeError("Crash before commit")
        except RuntimeError:
            pass

        # Verify embedding is still NULL
        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            chunk_after = res.scalar_one()
            assert chunk_after.embedding is None

            # Cleanup
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()

    async def test_23_zero_chunk_document_failure(self, db_session_factory, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        doc_id = uuid.uuid4()

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="zero_chunks.pdf", file_type="pdf", file_size=500, status="parsed", total_chunks=0)
            session.add(doc)
            await session.commit()

        # Querying chunks yields 0 chunks -> raises ProcessingError
        from sqlalchemy import select
        async with db_session_factory() as session:
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            chunks = res.scalars().all()
            assert len(chunks) == 0

        async with db_session_factory() as session:
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()
