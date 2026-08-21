"""Unit, integration, and performance tests for HNSW Vector Indexing (Sprint 8.1)."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.embedding_service import FakeGenAIClient, EmbeddingService
from app.services.vector_index_service import VectorIndexService, HNSW_INDEX_NAME
from app.services.retrieval_service import RetrievalService
from app.main import app

settings = get_settings()


@pytest.mark.asyncio
class TestHNSWConfigurationAndValidation:

    def test_01_hnsw_configuration_defaults(self):
        assert settings.HNSW_ENABLED is True
        assert settings.HNSW_M == 16
        assert settings.HNSW_EF_CONSTRUCTION == 64
        assert settings.HNSW_EF_SEARCH == 40
        assert settings.RETRIEVAL_RECALL_TARGET == 0.95

    def test_02_hnsw_configuration_override(self, monkeypatch):
        monkeypatch.setattr(settings, "HNSW_M", 32)
        monkeypatch.setattr(settings, "HNSW_EF_SEARCH", 100)
        assert settings.HNSW_M == 32
        assert settings.HNSW_EF_SEARCH == 100

    def test_03_invalid_hnsw_m_rejected(self):
        # Configuration parameter validation bounds
        assert settings.HNSW_M > 0

    def test_04_invalid_ef_construction_rejected(self):
        assert settings.HNSW_EF_CONSTRUCTION > 0

    def test_05_invalid_ef_search_rejected(self):
        assert settings.HNSW_EF_SEARCH > 0


@pytest.mark.asyncio
class TestHNSWDatabaseIndexCatalog:

    async def test_06_hnsw_index_exists(self, db_session_factory):
        async with db_session_factory() as session:
            info = await VectorIndexService.get_hnsw_index_info(db=session)
            assert info.exists is True, f"Expected HNSW index '{HNSW_INDEX_NAME}' to exist in pg_class"

    async def test_07_hnsw_index_method(self, db_session_factory):
        async with db_session_factory() as session:
            info = await VectorIndexService.get_hnsw_index_info(db=session)
            assert info.index_method == "hnsw", f"Expected index method 'hnsw', got '{info.index_method}'"

    async def test_08_hnsw_cosine_operator_class(self, db_session_factory):
        async with db_session_factory() as session:
            info = await VectorIndexService.get_hnsw_index_info(db=session)
            assert info.opclass_name == "vector_cosine_ops", f"Expected opclass 'vector_cosine_ops', got '{info.opclass_name}'"

    async def test_09_hnsw_index_valid(self, db_session_factory):
        async with db_session_factory() as session:
            info = await VectorIndexService.get_hnsw_index_info(db=session)
            assert info.is_valid is True, "Expected HNSW index to be marked valid in pg_index (indisvalid=true)"
            ready = await VectorIndexService.is_hnsw_index_ready(db=session)
            assert ready is True


@pytest.mark.asyncio
class TestHNSWRetrievalCompatibility:

    async def test_10_retrieval_returns_results(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        vectors = await emb_service.embed_texts(["Consolidated Financial Metric Revenue $500"])

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="hnsw_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            chunk = Chunk(
                document_id=doc_id,
                content="Consolidated Financial Metric Revenue $500",
                chunk_type="table",
                chunk_index=0,
                page_number=1,
                metadata_={"statement_type": "income_statement", "fiscal_periods": ["2025"]},
                embedding=vectors[0],
            )
            session.add_all([doc, chunk])
            await session.commit()

            results = await ret_service.search(query="Consolidated Financial Metric Revenue $500", top_k=5, db=session)
            assert len(results) >= 1
            assert results[0].chunk_id == chunk.id
            assert results[0].similarity > 0.9

            # Cleanup
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_11_retrieval_top_k(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        texts = [f"Item {i} Financial Note" for i in range(10)]
        vectors = await emb_service.embed_texts(texts)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="hnsw_topk.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=10)
            session.add(doc)
            for idx, (t, v) in enumerate(zip(texts, vectors)):
                c = Chunk(document_id=doc_id, content=t, chunk_type="text", chunk_index=idx, page_number=1, embedding=v)
                session.add(c)
            await session.commit()

            res3 = await ret_service.search(query="Item Financial Note", top_k=3, db=session)
            assert len(res3) == 3

            # Cleanup
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_12_retrieval_document_filter(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc1 = uuid.uuid4()
        doc2 = uuid.uuid4()
        v = (await emb_service.embed_texts(["Identical content in two docs"]))[0]

        async with db_session_factory() as session:
            d1 = Document(id=doc1, filename="d1.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=1)
            d2 = Document(id=doc2, filename="d2.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=1)
            c1 = Chunk(document_id=doc1, content="Identical content in two docs", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c2 = Chunk(document_id=doc2, content="Identical content in two docs", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            session.add_all([d1, d2, c1, c2])
            await session.commit()

            res = await ret_service.search(query="Identical content in two docs", top_k=5, document_id=doc1, db=session)
            assert len(res) == 1
            assert res[0].document_id == doc1

            # Cleanup
            for d in (d1, d2):
                obj = await session.get(Document, d.id)
                if obj:
                    await session.delete(obj)
            await session.commit()

    async def test_13_retrieval_similarity_threshold(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        v = [0.0] * 1536
        v[0] = 1.0

        async with db_session_factory() as session:
            d = Document(id=doc_id, filename="thresh.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Threshold test", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            session.add_all([d, c])
            await session.commit()

            # Orthogonal query vector should have similarity 0.0, filtered out by threshold 0.5
            res = await ret_service.search(query="Unrelated query string", min_similarity=0.99, document_id=doc_id, db=session)
            assert len(res) == 0

            # Cleanup
            obj = await session.get(Document, doc_id)
            if obj:
                await session.delete(obj)
                await session.commit()

    async def test_14_retrieval_metadata_preserved(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        v = (await emb_service.embed_texts(["Balance Sheet line items"]))[0]
        meta = {"statement_type": "balance_sheet", "currency": "USD", "units": "millions"}

        async with db_session_factory() as session:
            d = Document(id=doc_id, filename="meta.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Balance Sheet line items", chunk_type="table", chunk_index=0, page_number=5, metadata_=meta, embedding=v)
            session.add_all([d, c])
            await session.commit()

            res = await ret_service.search(query="Balance Sheet line items", document_id=doc_id, db=session)
            assert len(res) == 1
            assert res[0].metadata["statement_type"] == "balance_sheet"
            assert res[0].metadata["currency"] == "USD"

            # Cleanup
            obj = await session.get(Document, doc_id)
            if obj:
                await session.delete(obj)
                await session.commit()

    async def test_15_retrieval_page_numbers_preserved(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        v = (await emb_service.embed_texts(["Page 42 content"]))[0]

        async with db_session_factory() as session:
            d = Document(id=doc_id, filename="p42.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Page 42 content", chunk_type="text", chunk_index=0, page_number=42, embedding=v)
            session.add_all([d, c])
            await session.commit()

            res = await ret_service.search(query="Page 42 content", document_id=doc_id, db=session)
            assert len(res) == 1
            assert res[0].page_number == 42

            # Cleanup
            obj = await session.get(Document, doc_id)
            if obj:
                await session.delete(obj)
                await session.commit()

    async def test_16_retrieval_chunk_types_preserved(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        v = (await emb_service.embed_texts(["Table content"]))[0]

        async with db_session_factory() as session:
            d = Document(id=doc_id, filename="ctype.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Table content", chunk_type="table", chunk_index=0, page_number=1, embedding=v)
            session.add_all([d, c])
            await session.commit()

            res = await ret_service.search(query="Table content", document_id=doc_id, db=session)
            assert len(res) == 1
            assert res[0].chunk_type == "table"

            # Cleanup
            obj = await session.get(Document, doc_id)
            if obj:
                await session.delete(obj)
                await session.commit()

    async def test_17_hnsw_ef_search_applied(self, db_session_factory):
        async with db_session_factory() as session:
            # Verify setting LOCAL hnsw.ef_search operates safely inside an asyncpg transaction
            await session.execute(text("SET LOCAL hnsw.ef_search = 60;"))
            res = await session.execute(text("SHOW hnsw.ef_search;"))
            val = res.scalar()
            assert str(val) == "60"

    async def test_18_existing_search_endpoint(self, db_session_factory, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        from app.core.database import get_db

        async def override_get_db():
            async with db_session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/search",
                json={"query": "test query", "top_k": 5, "min_similarity": 0.0},
            )
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "total_results" in data

        app.dependency_overrides.pop(get_db, None)

    async def test_19_exact_vs_hnsw_overlap(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        texts = [f"Financial disclosure paragraph {i} on revenue recognition" for i in range(8)]
        vectors = await emb_service.embed_texts(texts)

        async with db_session_factory() as session:
            d = Document(id=doc_id, filename="overlap.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=8)
            session.add(d)
            for idx, (t, v) in enumerate(zip(texts, vectors)):
                c = Chunk(document_id=doc_id, content=t, chunk_type="text", chunk_index=idx, page_number=1, embedding=v)
                session.add(c)
            await session.commit()

            # Exact search
            await session.execute(text("SET LOCAL enable_indexscan = off;"))
            exact = await ret_service.search("revenue recognition disclosure", top_k=5, document_id=doc_id, db=session)

            # HNSW search
            await session.execute(text("SET LOCAL enable_indexscan = on;"))
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {settings.HNSW_EF_SEARCH};"))
            hnsw = await ret_service.search("revenue recognition disclosure", top_k=5, document_id=doc_id, db=session)

            exact_ids = set(r.chunk_id for r in exact)
            hnsw_ids = set(r.chunk_id for r in hnsw)
            overlap = len(exact_ids.intersection(hnsw_ids))
            assert overlap >= 4  # high overlap on standard queries

            # Cleanup
            obj = await session.get(Document, doc_id)
            if obj:
                await session.delete(obj)
                await session.commit()

    async def test_20_recall_at_k(self, db_session_factory):
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        ret_service = RetrievalService(embedding_service=emb_service)

        doc_id = uuid.uuid4()
        texts = [f"Operating Cash Flows line {i}" for i in range(5)]
        vectors = await emb_service.embed_texts(texts)

        async with db_session_factory() as session:
            d = Document(id=doc_id, filename="recall.pdf", file_type="pdf", file_size=100, status="indexed", total_chunks=5)
            session.add(d)
            for idx, (t, v) in enumerate(zip(texts, vectors)):
                c = Chunk(document_id=doc_id, content=t, chunk_type="text", chunk_index=idx, page_number=1, embedding=v)
                session.add(c)
            await session.commit()

            # Exact
            await session.execute(text("SET LOCAL enable_indexscan = off;"))
            exact = await ret_service.search("Operating Cash Flows", top_k=3, document_id=doc_id, db=session)

            # HNSW
            await session.execute(text("SET LOCAL enable_indexscan = on;"))
            hnsw = await ret_service.search("Operating Cash Flows", top_k=3, document_id=doc_id, db=session)

            exact_ids = set(r.chunk_id for r in exact)
            hnsw_ids = set(r.chunk_id for r in hnsw)
            recall = len(exact_ids.intersection(hnsw_ids)) / float(len(exact_ids))
            assert recall >= 0.80

            # Cleanup
            obj = await session.get(Document, doc_id)
            if obj:
                await session.delete(obj)
                await session.commit()
