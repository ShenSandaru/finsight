import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.core.exceptions import ValidationError, ProcessingError
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.embedding_service import EmbeddingService, FakeGenAIClient
from app.services.retrieval_service import RetrievalService, RetrievalResult
from app.main import app

settings = get_settings()


def create_deterministic_unit_vector(active_dimension: int, total_dim: int = 1536) -> list[float]:
    """Helper to create an exact one-hot unit vector in R^1536."""
    vec = [0.0] * total_dim
    vec[active_dimension % total_dim] = 1.0
    return vec


class TestRetrievalUnitAndValidation:

    @pytest.mark.asyncio
    async def test_01_query_embedding_uses_retrieval_query(self):
        class CaptureConfigClient:
            def __init__(self):
                self.captured_config = None
                self.aio = self

            class Models:
                def __init__(self, parent):
                    self.parent = parent

                async def embed_content(self, model, contents, config=None):
                    self.parent.captured_config = config
                    fake = FakeGenAIClient()
                    return await fake.models.embed_content(model, contents, config)

            @property
            def models(self):
                return self.Models(self)

        capturer = CaptureConfigClient()
        service = EmbeddingService(client=capturer)
        vec = await service.embed_query("What was the annual revenue?")
        assert len(vec) == 1536
        assert capturer.captured_config is not None
        assert capturer.captured_config.task_type == "RETRIEVAL_QUERY"
        assert capturer.captured_config.output_dimensionality == 1536

    @pytest.mark.asyncio
    async def test_02_query_embedding_dimension_validation(self):
        bad_dim_client = FakeGenAIClient(dimension=768)
        service = EmbeddingService(client=bad_dim_client, dimensions=1536)
        with pytest.raises(ProcessingError) as exc_info:
            await service.embed_query("Valid query string")
        assert "dimension mismatch" in str(exc_info.value).lower() or "invalid embedding dimension" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_03_empty_query_rejection(self):
        service = RetrievalService()
        with pytest.raises(ValidationError) as exc_info:
            await service.search(query="")
        assert "non-empty string" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_04_whitespace_query_rejection(self):
        service = RetrievalService()
        with pytest.raises(ValidationError) as exc_info:
            await service.search(query="   \t\n  ")
        assert "non-empty string" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_05_top_k_maximum_validation(self):
        service = RetrievalService()
        with pytest.raises(ValidationError) as exc_info:
            await service.search(query="Valid query", top_k=25)
        assert "between 1 and 20" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_06_top_k_minimum_validation(self):
        service = RetrievalService()
        with pytest.raises(ValidationError) as exc_info:
            await service.search(query="Valid query", top_k=0)
        assert "between 1 and 20" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_07_invalid_similarity_threshold(self):
        service = RetrievalService()
        with pytest.raises(ValidationError) as exc_info:
            await service.search(query="Valid query", min_similarity=1.5)
        assert "between 0.0 and 1.0" in str(exc_info.value).lower()


@pytest.mark.asyncio
class TestRetrievalDatabaseIntegration:

    async def test_08_basic_similarity_search(self, db_session_factory):
        doc_id = uuid.uuid4()
        v_target = create_deterministic_unit_vector(0)
        v_other = create_deterministic_unit_vector(1)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="retrieval_basic.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=2)
            c1 = Chunk(document_id=doc_id, content="Target content", chunk_type="text", chunk_index=0, page_number=1, embedding=v_target)
            c2 = Chunk(document_id=doc_id, content="Other content", chunk_type="text", chunk_index=1, page_number=1, embedding=v_other)
            session.add_all([doc, c1, c2])
            await session.commit()

        class MockTargetEmbeddingService:
            async def embed_query(self, query: str) -> list[float]:
                return v_target

            async def close(self):
                pass

        service = RetrievalService(
            embedding_service=MockTargetEmbeddingService(),
            session_factory=db_session_factory,
        )

        results = await service.search("Query for target", top_k=5, document_id=doc_id)
        assert len(results) == 2
        # Highest similarity chunk should be c1 with similarity 1.0
        assert results[0].content == "Target content"
        assert pytest.approx(results[0].similarity, 0.001) == 1.0
        # Orthogonal vector has cosine distance 1.0, so similarity = 0.0
        assert results[1].content == "Other content"
        assert pytest.approx(results[1].similarity, 0.001) == 0.0

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_09_results_ordered_by_similarity(self, db_session_factory):
        doc_id = uuid.uuid4()
        # Query vector: [1, 0, 0, ...]
        v_query = create_deterministic_unit_vector(0)
        # High similarity (angle 0 deg -> cos = 1.0 -> sim = 1.0)
        v_high = create_deterministic_unit_vector(0)
        # Medium similarity (approx 45 deg -> cos = 0.707 -> sim = 0.707)
        v_med = [0.0] * 1536
        v_med[0] = 0.70710678
        v_med[1] = 0.70710678
        # Low similarity (angle 90 deg -> cos = 0.0 -> sim = 0.0)
        v_low = create_deterministic_unit_vector(1)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="order_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=3)
            c_low = Chunk(document_id=doc_id, content="Low similarity", chunk_type="text", chunk_index=0, page_number=1, embedding=v_low)
            c_high = Chunk(document_id=doc_id, content="High similarity", chunk_type="text", chunk_index=1, page_number=1, embedding=v_high)
            c_med = Chunk(document_id=doc_id, content="Med similarity", chunk_type="text", chunk_index=2, page_number=1, embedding=v_med)
            session.add_all([doc, c_low, c_high, c_med])
            await session.commit()

        class MockQueryEmbeddingService:
            async def embed_query(self, query: str) -> list[float]:
                return v_query

            async def close(self):
                pass

        service = RetrievalService(
            embedding_service=MockQueryEmbeddingService(),
            session_factory=db_session_factory,
        )

        results = await service.search("Order query", top_k=5, document_id=doc_id)
        assert len(results) == 3
        assert results[0].content == "High similarity"
        assert results[1].content == "Med similarity"
        assert results[2].content == "Low similarity"
        assert results[0].similarity > results[1].similarity > results[2].similarity

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_10_top_k_limit(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="limit_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=5)
            chunks = [
                Chunk(document_id=doc_id, content=f"Chunk {i}", chunk_type="text", chunk_index=i, page_number=1, embedding=create_deterministic_unit_vector(i))
                for i in range(5)
            ]
            session.add_all([doc, *chunks])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return create_deterministic_unit_vector(0)

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Query", top_k=2, document_id=doc_id)
        assert len(results) == 2

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_11_min_similarity_filter(self, db_session_factory):
        doc_id = uuid.uuid4()
        v_high = create_deterministic_unit_vector(0)  # sim = 1.0
        v_low = create_deterministic_unit_vector(1)   # sim = 0.0

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="threshold_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=2)
            c1 = Chunk(document_id=doc_id, content="High match", chunk_type="text", chunk_index=0, page_number=1, embedding=v_high)
            c2 = Chunk(document_id=doc_id, content="Low match", chunk_type="text", chunk_index=1, page_number=1, embedding=v_low)
            session.add_all([doc, c1, c2])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v_high

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Query", min_similarity=0.5, document_id=doc_id)
        assert len(results) == 1
        assert results[0].content == "High match"

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_12_document_id_filter(self, db_session_factory):
        doc_id_1 = uuid.uuid4()
        doc_id_2 = uuid.uuid4()
        v = create_deterministic_unit_vector(0)

        async with db_session_factory() as session:
            doc1 = Document(id=doc_id_1, filename="doc1.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            doc2 = Document(id=doc_id_2, filename="doc2.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c1 = Chunk(document_id=doc_id_1, content="Doc 1 chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c2 = Chunk(document_id=doc_id_2, content="Doc 2 chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            session.add_all([doc1, doc2, c1, c2])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Query", document_id=doc_id_1)
        assert len(results) == 1
        assert results[0].document_id == doc_id_1
        assert results[0].content == "Doc 1 chunk"

        # Cleanup
        async with db_session_factory() as session:
            for did in (doc_id_1, doc_id_2):
                doc_obj = await session.get(Document, did)
                if doc_obj:
                    await session.delete(doc_obj)
            await session.commit()

    async def test_13_cross_document_search(self, db_session_factory):
        doc_id_1 = uuid.uuid4()
        doc_id_2 = uuid.uuid4()
        v = create_deterministic_unit_vector(0)

        async with db_session_factory() as session:
            doc1 = Document(id=doc_id_1, filename="cross1.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            doc2 = Document(id=doc_id_2, filename="cross2.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c1 = Chunk(document_id=doc_id_1, content="Cross 1 chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c2 = Chunk(document_id=doc_id_2, content="Cross 2 chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            session.add_all([doc1, doc2, c1, c2])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Query", document_id=None, top_k=20)
        found_docs = {r.document_id for r in results}
        assert doc_id_1 in found_docs
        assert doc_id_2 in found_docs

        # Cleanup
        async with db_session_factory() as session:
            for did in (doc_id_1, doc_id_2):
                doc_obj = await session.get(Document, did)
                if doc_obj:
                    await session.delete(doc_obj)
            await session.commit()

    async def test_14_null_embeddings_excluded(self, db_session_factory):
        doc_id = uuid.uuid4()
        v = create_deterministic_unit_vector(0)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="null_check.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=2)
            c_valid = Chunk(document_id=doc_id, content="Valid embedding", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c_null = Chunk(document_id=doc_id, content="Null embedding", chunk_type="text", chunk_index=1, page_number=1, embedding=None)
            session.add_all([doc, c_valid, c_null])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Query", top_k=10, document_id=doc_id)
        contents = [r.content for r in results]
        assert "Valid embedding" in contents
        assert "Null embedding" not in contents

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_15_non_indexed_documents_excluded(self, db_session_factory):
        doc_id_indexed = uuid.uuid4()
        doc_id_parsed = uuid.uuid4()
        doc_id_failed = uuid.uuid4()
        v = create_deterministic_unit_vector(0)

        async with db_session_factory() as session:
            doc_idx = Document(id=doc_id_indexed, filename="idx.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            doc_prs = Document(id=doc_id_parsed, filename="prs.pdf", file_type="pdf", file_size=1000, status="parsed", total_chunks=1)
            doc_fld = Document(id=doc_id_failed, filename="fld.pdf", file_type="pdf", file_size=1000, status="failed", total_chunks=1)
            
            c_idx = Chunk(document_id=doc_id_indexed, content="Indexed chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c_prs = Chunk(document_id=doc_id_parsed, content="Parsed chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c_fld = Chunk(document_id=doc_id_failed, content="Failed chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            
            session.add_all([doc_idx, doc_prs, doc_fld, c_idx, c_prs, c_fld])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Query", top_k=20)
        found_doc_ids = {r.document_id for r in results}
        assert doc_id_indexed in found_doc_ids
        assert doc_id_parsed not in found_doc_ids
        assert doc_id_failed not in found_doc_ids

        # Cleanup
        async with db_session_factory() as session:
            for did in (doc_id_indexed, doc_id_parsed, doc_id_failed):
                doc_obj = await session.get(Document, did)
                if doc_obj:
                    await session.delete(doc_obj)
            await session.commit()

    async def test_16_result_metadata_page_number_and_type_preserved(self, db_session_factory):
        doc_id = uuid.uuid4()
        v = create_deterministic_unit_vector(0)
        table_meta = {
            "statement_type": "income_statement",
            "fiscal_periods": ["2025", "2024"],
            "currency": "USD",
            "confidence": 0.95,
        }

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="meta_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c = Chunk(
                document_id=doc_id,
                content="| Revenue | $1000 |\n| Net Income | $200 |",
                chunk_type="table",
                chunk_index=3,
                page_number=2,
                metadata_=table_meta,
                embedding=v,
            )
            session.add_all([doc, c])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Revenue query", top_k=5, document_id=doc_id)
        assert len(results) == 1
        res = results[0]
        assert res.chunk_type == "table"
        assert res.chunk_index == 3
        assert res.page_number == 2
        assert res.metadata.get("statement_type") == "income_statement"
        assert res.metadata.get("fiscal_periods") == ["2025", "2024"]

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_17_deterministic_tie_ordering(self, db_session_factory):
        doc_id = uuid.uuid4()
        v = create_deterministic_unit_vector(0)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="tie_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=3)
            c0 = Chunk(document_id=doc_id, content="Index 0", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c1 = Chunk(document_id=doc_id, content="Index 1", chunk_type="text", chunk_index=1, page_number=1, embedding=v)
            c2 = Chunk(document_id=doc_id, content="Index 2", chunk_type="text", chunk_index=2, page_number=1, embedding=v)
            session.add_all([doc, c2, c0, c1])  # added out of order
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Tie query", top_k=5, document_id=doc_id)
        assert len(results) == 3
        assert [r.chunk_index for r in results] == [0, 1, 2]

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_18_no_results_when_all_below_threshold(self, db_session_factory):
        doc_id = uuid.uuid4()
        v_low = create_deterministic_unit_vector(1)  # orthogonal, sim = 0.0

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="no_res.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Low similarity chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v_low)
            session.add_all([doc, c])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return create_deterministic_unit_vector(0)

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Threshold query", top_k=5, min_similarity=0.5, document_id=doc_id)
        assert len(results) == 0

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_18b_multi_document_ids_filtering(self, db_session_factory):
        """Sprint 10.3: Test multi-document filtering and isolation across Documents A, B, and C."""
        doc_a_id = uuid.uuid4()
        doc_b_id = uuid.uuid4()
        doc_c_id = uuid.uuid4()
        v = create_deterministic_unit_vector(0)

        async with db_session_factory() as session:
            doc_a = Document(id=doc_a_id, filename="doc_a.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            doc_b = Document(id=doc_b_id, filename="doc_b.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            doc_c = Document(id=doc_c_id, filename="doc_c.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            
            c_a = Chunk(document_id=doc_a_id, content="Doc A Content", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c_b = Chunk(document_id=doc_b_id, content="Doc B Content", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c_c = Chunk(document_id=doc_c_id, content="Doc C Content", chunk_type="text", chunk_index=0, page_number=1, embedding=v)

            session.add_all([doc_a, doc_b, doc_c, c_a, c_b, c_c])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        
        # 1. Search with document_ids=[doc_a_id, doc_b_id] -> only A and B returned, C never returned
        results = await service.search("Multi-doc query", top_k=5, document_ids=[doc_a_id, doc_b_id])
        assert len(results) == 2
        retrieved_doc_ids = {r.document_id for r in results}
        assert doc_a_id in retrieved_doc_ids
        assert doc_b_id in retrieved_doc_ids
        assert doc_c_id not in retrieved_doc_ids

        # 2. Backward compatibility: single document_id filter
        single_results = await service.search("Single doc query", top_k=5, document_id=doc_c_id)
        assert len(single_results) == 1
        assert single_results[0].document_id == doc_c_id

        # Cleanup
        async with db_session_factory() as session:
            for d_id in [doc_a_id, doc_b_id, doc_c_id]:
                d_obj = await session.get(Document, d_id)
                if d_obj:
                    await session.delete(d_obj)
            await session.commit()


@pytest.mark.asyncio
class TestSearchAPIEndpoint:

    async def test_19_api_search_endpoint_success(self, db_session_factory, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        from app.core.database import get_db

        async def override_get_db():
            async with db_session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        doc_id = uuid.uuid4()
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        # Generate deterministic vector for sample text
        vectors = await emb_service.embed_texts(["Consolidated Financial Income Statement"])

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="api_search.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c = Chunk(
                document_id=doc_id,
                content="Consolidated Financial Income Statement",
                chunk_type="table",
                chunk_index=0,
                page_number=1,
                metadata_={"statement_type": "income_statement"},
                embedding=vectors[0],
            )
            session.add_all([doc, c])
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/search",
                json={
                    "query": "Consolidated Financial Income Statement",
                    "top_k": 5,
                    "min_similarity": 0.0,
                    "document_id": str(doc_id),
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "Consolidated Financial Income Statement"
            assert data["total_results"] >= 1
            first = data["results"][0]
            assert "chunk_id" in first
            assert "document_id" in first
            assert first["chunk_type"] == "table"
            assert first["metadata"]["statement_type"] == "income_statement"
            assert 0.0 <= first["similarity"] <= 1.0

        app.dependency_overrides.pop(get_db, None)

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_20_api_search_with_document_filter(self, db_session_factory, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        from app.core.database import get_db

        async def override_get_db():
            async with db_session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        doc_id_1 = uuid.uuid4()
        doc_id_2 = uuid.uuid4()
        fake_client = FakeGenAIClient()
        emb_service = EmbeddingService(client=fake_client)
        v = (await emb_service.embed_texts(["Common text"]))[0]

        async with db_session_factory() as session:
            doc1 = Document(id=doc_id_1, filename="api_doc1.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            doc2 = Document(id=doc_id_2, filename="api_doc2.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c1 = Chunk(document_id=doc_id_1, content="Common text", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            c2 = Chunk(document_id=doc_id_2, content="Common text", chunk_type="text", chunk_index=0, page_number=1, embedding=v)
            session.add_all([doc1, doc2, c1, c2])
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/search",
                json={
                    "query": "Common text",
                    "top_k": 5,
                    "document_id": str(doc_id_1),
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_results"] == 1
            assert data["results"][0]["document_id"] == str(doc_id_1)

        app.dependency_overrides.pop(get_db, None)

        # Cleanup
        async with db_session_factory() as session:
            for did in (doc_id_1, doc_id_2):
                doc_obj = await session.get(Document, did)
                if doc_obj:
                    await session.delete(doc_obj)
            await session.commit()

    async def test_21_api_invalid_request_validation(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Empty query
            res1 = await client.post("/api/v1/search", json={"query": "", "top_k": 5})
            assert res1.status_code in (400, 422)

            # top_k out of bounds
            res2 = await client.post("/api/v1/search", json={"query": "Valid query", "top_k": 50})
            assert res2.status_code in (400, 422)

            # min_similarity out of bounds
            res3 = await client.post("/api/v1/search", json={"query": "Valid query", "min_similarity": 2.0})
            assert res3.status_code in (400, 422)

    async def test_22_api_no_answer_generated(self, db_session_factory, monkeypatch):
        """Confirm the API response contains chunk results only and does not generate RAG answer text."""
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
                json={"query": "Sample question", "top_k": 5},
            )
            assert response.status_code == 200
            data = response.json()
            assert "answer" not in data
            assert "response" not in data
            assert "summary" not in data
            assert "results" in data

        app.dependency_overrides.pop(get_db, None)

    async def test_23_similarity_score_range(self, db_session_factory):
        """Confirm all calculated similarity scores strictly fall within [-1.0, 1.0]."""
        doc_id = uuid.uuid4()
        v1 = create_deterministic_unit_vector(0)
        v2 = create_deterministic_unit_vector(1)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="range_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=2)
            c1 = Chunk(document_id=doc_id, content="Range 1", chunk_type="text", chunk_index=0, page_number=1, embedding=v1)
            c2 = Chunk(document_id=doc_id, content="Range 2", chunk_type="text", chunk_index=1, page_number=1, embedding=v2)
            session.add_all([doc, c1, c2])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v1

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Range query", top_k=5, document_id=doc_id)
        for r in results:
            assert -1.0 <= r.similarity <= 1.0

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_24_database_similarity_query(self, db_session_factory):
        """Directly verify PostgreSQL pgvector <=> distance evaluation matches mathematical expectation."""
        doc_id = uuid.uuid4()
        v_exact = create_deterministic_unit_vector(0)

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="math_test.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c = Chunk(document_id=doc_id, content="Exact match chunk", chunk_type="text", chunk_index=0, page_number=1, embedding=v_exact)
            session.add_all([doc, c])
            await session.commit()

        class MockEmbService:
            async def embed_query(self, query: str) -> list[float]:
                return v_exact

            async def close(self):
                pass

        service = RetrievalService(embedding_service=MockEmbService(), session_factory=db_session_factory)
        results = await service.search("Exact query", top_k=1, document_id=doc_id)
        assert len(results) == 1
        assert pytest.approx(results[0].similarity, 0.0001) == 1.0

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

