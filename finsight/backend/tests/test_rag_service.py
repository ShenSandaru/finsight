"""Comprehensive unit, database integration, and API test suite for RAGService (Sprint 7.1)."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.core.exceptions import ValidationError, ProcessingError
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.embedding_service import FakeGenAIClient
from app.services.retrieval_service import RetrievalService, RetrievalResult
from app.services.generation_service import GenerationService, GROUNDING_SYSTEM_INSTRUCTION
from app.services.rag_service import RAGService, build_context, validate_and_clean_citations, INSUFFICIENT_EVIDENCE_ANSWER
from app.main import app

settings = get_settings()


class MockRetrievalService:
    def __init__(self, return_results: list[RetrievalResult] | None = None, raise_error: Exception | None = None):
        self.return_results = return_results if return_results is not None else []
        self.raise_error = raise_error
        self.called_query = None
        self.called_top_k = None
        self.called_min_similarity = None
        self.called_doc_id = None
        self.embedding_service = FakeEmbeddingService()

    async def search(self, query: str, top_k: int = 5, min_similarity: float | None = None, document_id: uuid.UUID | None = None, document_ids: list[uuid.UUID] | None = None, user_id: uuid.UUID | None = None, db=None, **kwargs) -> list[RetrievalResult]:
        self.called_query = query
        self.called_top_k = top_k
        self.called_min_similarity = min_similarity
        self.called_doc_id = document_id
        self.called_user_id = user_id
        if self.raise_error:
            raise self.raise_error
        return self.return_results


class FakeEmbeddingService:
    async def close(self):
        pass


class MockGenerationService:
    def __init__(self, return_answer: str = "Mocked answer [SOURCE 1]", raise_error: Exception | None = None):
        self.return_answer = return_answer
        self.raise_error = raise_error
        self.called_query = None
        self.called_context = None

    async def generate_answer(self, query: str, context: str) -> str:
        self.called_query = query
        self.called_context = context
        if self.raise_error:
            raise self.raise_error
        return self.return_answer

    async def close(self):
        pass


def make_sample_retrieval_result(
    index: int = 0,
    chunk_type: str = "table",
    content: str = "| Total Revenue | $1,000 |",
    page_number: int = 1,
    similarity: float = 0.85,
    statement_type: str | None = "income_statement",
    fiscal_periods: list[str] | None = None,
    currency: str = "USD",
    units: str = "millions",
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        chunk_type=chunk_type,
        chunk_index=index,
        page_number=page_number,
        similarity=similarity,
        metadata={
            "statement_type": statement_type,
            "fiscal_periods": fiscal_periods or ["2025", "2024"],
            "currency": currency,
            "units": units,
        },
    )


@pytest.mark.asyncio
class TestRAGUnitAndContextAssembly:

    async def test_01_basic_rag_answer(self):
        sample = make_sample_retrieval_result()
        retrieval = MockRetrievalService([sample])
        generation = MockGenerationService("Revenue was $1,000 million in 2025. [SOURCE 1]")
        rag = RAGService(retrieval_service=retrieval, generation_service=generation)

        response = await rag.answer("What was revenue in 2025?")
        assert response.grounded is True
        assert response.retrieved_chunks == 1
        assert "Revenue was $1,000 million" in response.answer
        assert len(response.citations) == 1
        assert response.citations[0].chunk_id == sample.chunk_id
        assert response.citations[0].statement_type == "income_statement"

    async def test_02_query_validation(self):
        rag = RAGService(retrieval_service=MockRetrievalService(), generation_service=MockGenerationService())
        with pytest.raises(ValidationError) as exc:
            await rag.answer(query="")
        assert "non-empty string" in str(exc.value).lower()

    async def test_03_empty_query(self):
        rag = RAGService(retrieval_service=MockRetrievalService(), generation_service=MockGenerationService())
        with pytest.raises(ValidationError) as exc:
            await rag.answer(query="   \t\n  ")
        assert "non-empty string" in str(exc.value).lower()

    async def test_04_retrieval_service_called(self):
        retrieval = MockRetrievalService([make_sample_retrieval_result()])
        generation = MockGenerationService()
        rag = RAGService(retrieval_service=retrieval, generation_service=generation)

        await rag.answer("What was revenue?", top_k=3, min_similarity=0.45)
        assert retrieval.called_query == "What was revenue?"
        assert retrieval.called_top_k == 3
        assert retrieval.called_min_similarity == 0.45

    async def test_05_generation_service_called(self):
        sample = make_sample_retrieval_result()
        retrieval = MockRetrievalService([sample])
        generation = MockGenerationService()
        rag = RAGService(retrieval_service=retrieval, generation_service=generation)

        await rag.answer("Test question")
        assert generation.called_query == "Test question"
        assert generation.called_context is not None
        assert "[SOURCE 1]" in generation.called_context

    async def test_06_context_contains_retrieved_chunks(self):
        s1 = make_sample_retrieval_result(index=0, content="Revenue content")
        s2 = make_sample_retrieval_result(index=1, content="Assets content")
        context_str, citations = build_context([s1, s2])
        assert "[SOURCE 1]" in context_str
        assert "[SOURCE 2]" in context_str
        assert "Revenue content" in context_str
        assert "Assets content" in context_str
        assert len(citations) == 2

    async def test_07_context_preserves_page_numbers(self):
        s = make_sample_retrieval_result(page_number=42)
        context_str, citations = build_context([s])
        assert "Page: 42" in context_str
        assert citations[0].page_number == 42

    async def test_08_context_preserves_table_metadata(self):
        s = make_sample_retrieval_result(statement_type="balance_sheet", chunk_type="table")
        context_str, citations = build_context([s])
        assert "Chunk Type: table" in context_str
        assert "Statement Type: balance_sheet" in context_str
        assert citations[0].statement_type == "balance_sheet"

    async def test_09_context_preserves_fiscal_periods(self):
        s = make_sample_retrieval_result(fiscal_periods=["2025", "2024", "2023"])
        context_str, citations = build_context([s])
        assert "Fiscal Periods: 2025, 2024, 2023" in context_str
        assert citations[0].fiscal_periods == ["2025", "2024", "2023"]

    async def test_10_context_preserves_currency_and_units(self):
        s = make_sample_retrieval_result(currency="EUR", units="thousands")
        context_str, _ = build_context([s])
        assert "Currency: EUR" in context_str
        assert "Units: thousands" in context_str

    async def test_11_context_max_character_limit(self):
        # Create 5 large samples
        samples = [make_sample_retrieval_result(index=i, content="A" * 500) for i in range(5)]
        # Cap max_chars at 800 (only enough for 1 block)
        context_str, citations = build_context(samples, max_chars=800)
        assert len(citations) == 1
        assert "[SOURCE 1]" in context_str
        assert "[SOURCE 2]" not in context_str

    async def test_12_context_does_not_split_chunk(self):
        # A single chunk whose block length exceeds max_chars should not be included or sliced
        sample = make_sample_retrieval_result(content="A" * 1000)
        context_str, citations = build_context([sample], max_chars=100)
        assert context_str == ""
        assert len(citations) == 0

    async def test_13_citations_match_retrieved_chunks(self):
        s1 = make_sample_retrieval_result(index=0)
        s2 = make_sample_retrieval_result(index=1)
        _, citations = build_context([s1, s2])
        assert citations[0].chunk_id == s1.chunk_id
        assert citations[1].chunk_id == s2.chunk_id
        assert citations[0].similarity == s1.similarity
        assert citations[1].similarity == s2.similarity

    async def test_14_similarity_threshold_passed_to_retrieval(self):
        retrieval = MockRetrievalService([make_sample_retrieval_result()])
        rag = RAGService(retrieval_service=retrieval, generation_service=MockGenerationService())
        await rag.answer("Query", min_similarity=0.65)
        assert retrieval.called_min_similarity == 0.65

    async def test_15_no_results_does_not_call_gemini(self):
        retrieval = MockRetrievalService([])  # zero results returned
        generation = MockGenerationService()
        rag = RAGService(retrieval_service=retrieval, generation_service=generation)

        response = await rag.answer("Unanswerable question")
        assert generation.called_query is None  # LLM never invoked
        assert response.grounded is False
        assert response.retrieved_chunks == 0
        assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
        assert response.citations == []

    async def test_16_grounded_flag_true(self):
        retrieval = MockRetrievalService([make_sample_retrieval_result()])
        rag = RAGService(retrieval_service=retrieval, generation_service=MockGenerationService("Answer [SOURCE 1]"))
        response = await rag.answer("Valid question")
        assert response.grounded is True

    async def test_17_grounded_flag_false(self):
        retrieval = MockRetrievalService([])
        rag = RAGService(retrieval_service=retrieval, generation_service=MockGenerationService())
        response = await rag.answer("Query with no hits")
        assert response.grounded is False

    async def test_18_generation_failure(self):
        retrieval = MockRetrievalService([make_sample_retrieval_result()])
        generation = MockGenerationService(raise_error=ProcessingError(message="Gemini API rate limit exceeded"))
        rag = RAGService(retrieval_service=retrieval, generation_service=generation)
        with pytest.raises(ProcessingError) as exc:
            await rag.answer("Test query")
        assert "rate limit exceeded" in str(exc.value).lower()

    async def test_19_retrieval_failure(self):
        retrieval = MockRetrievalService(raise_error=ProcessingError(message="Database connection error"))
        generation = MockGenerationService()
        rag = RAGService(retrieval_service=retrieval, generation_service=generation)
        with pytest.raises(ProcessingError) as exc:
            await rag.answer("Test query")
        assert "database connection error" in str(exc.value).lower()

    async def test_20_prompt_contains_grounding_rules(self):
        assert "Never use outside knowledge" in GROUNDING_SYSTEM_INSTRUCTION
        assert "Never invent financial values" in GROUNDING_SYSTEM_INSTRUCTION
        assert "[SOURCE N]" in GROUNDING_SYSTEM_INSTRUCTION

    async def test_21_prompt_contains_source_identifiers(self):
        s = make_sample_retrieval_result()
        context, _ = build_context([s])
        assert "[SOURCE 1]" in context
        assert "Document ID:" in context

    async def test_22_fake_gemini_generation(self):
        fake_client = FakeGenAIClient()
        gen_service = GenerationService(client=fake_client)
        ans = await gen_service.generate_answer("What was revenue?", "[SOURCE 1] Revenue $1000")
        assert len(ans) > 0
        assert "[SOURCE 1]" in ans

    async def test_23_empty_generation_response(self):
        class EmptyGenClient:
            def __init__(self):
                self.aio = self

            class Models:
                def __init__(self, parent):
                    pass

                async def generate_content(self, model, contents, config=None):
                    class EmptyResponse:
                        text = ""
                    return EmptyResponse()

            @property
            def models(self):
                return self.Models(self)

        gen_service = GenerationService(client=EmptyGenClient())
        with pytest.raises(ProcessingError) as exc:
            await gen_service.generate_answer("Query", "Context")
        assert "empty or blank" in str(exc.value).lower()

    async def test_24_invalid_source_citation_handling(self):
        # If Gemini generates [SOURCE 99] when only 2 sources exist, it should be cleanly stripped
        raw = "Revenue was $1000 [SOURCE 1] but profit was $200 [SOURCE 99]."
        cleaned = validate_and_clean_citations(raw, num_valid_sources=2)
        assert "[SOURCE 1]" in cleaned
        assert "[SOURCE 99]" not in cleaned

    async def test_25_no_api_key_leakage(self):
        gen_service = GenerationService(client=FakeGenAIClient())
        try:
            await gen_service.generate_answer("", "")
        except ValidationError as exc:
            assert settings.GEMINI_API_KEY not in str(exc)
            assert "api_key" not in str(exc).lower()

    async def test_26_top_k_validation(self):
        rag = RAGService(retrieval_service=MockRetrievalService(), generation_service=MockGenerationService())
        with pytest.raises(ValidationError):
            await rag.answer("Query", top_k=0)
        with pytest.raises(ValidationError):
            await rag.answer("Query", top_k=50)

    async def test_27_min_similarity_validation(self):
        rag = RAGService(retrieval_service=MockRetrievalService(), generation_service=MockGenerationService())
        with pytest.raises(ValidationError):
            await rag.answer("Query", min_similarity=1.5)
        with pytest.raises(ValidationError):
            await rag.answer("Query", min_similarity=-0.2)


@pytest.mark.asyncio
class TestRAGAPIEndpoint:

    async def test_28_api_rag_endpoint_success(self, db_session_factory, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        monkeypatch.setattr(settings, "GEMINI_GENERATION_PROVIDER", "fake")
        from app.core.database import get_db

        async def override_get_db():
            async with db_session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        doc_id = uuid.uuid4()
        fake_client = FakeGenAIClient()
        from app.services.embedding_service import EmbeddingService
        emb_service = EmbeddingService(client=fake_client)
        vectors = await emb_service.embed_texts(["Consolidated Statements of Operations Revenue $1,000"])

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="rag_api.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c = Chunk(
                document_id=doc_id,
                content="Consolidated Statements of Operations Revenue $1,000",
                chunk_type="table",
                chunk_index=0,
                page_number=1,
                metadata_={"statement_type": "income_statement", "fiscal_periods": ["2025"]},
                embedding=vectors[0],
            )
            session.add_all([doc, c])
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/rag/query",
                json={
                    "query": "Consolidated Statements of Operations Revenue $1,000",
                    "top_k": 5,
                    "min_similarity": 0.0,
                    "document_id": str(doc_id),
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "Consolidated Statements of Operations Revenue $1,000"
            assert data["grounded"] is True
            assert len(data["answer"]) > 0
            assert data["retrieved_chunks"] >= 1
            assert len(data["citations"]) >= 1
            cit = data["citations"][0]
            assert cit["document_id"] == str(doc_id)
            assert cit["statement_type"] == "income_statement"
            assert cit["page_number"] == 1

        app.dependency_overrides.pop(get_db, None)

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_29_api_rag_insufficient_evidence(self, db_session_factory, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "fake")
        monkeypatch.setattr(settings, "GEMINI_GENERATION_PROVIDER", "fake")
        from app.core.database import get_db

        async def override_get_db():
            async with db_session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        # Create a document whose chunk is orthogonal to the test query
        doc_id = uuid.uuid4()
        v_low = [0.0] * 1536
        v_low[1] = 1.0  # orthogonal vector

        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="unmatched.pdf", file_type="pdf", file_size=1000, status="indexed", total_chunks=1)
            c = Chunk(
                document_id=doc_id,
                content="Unrelated narrative text without numbers",
                chunk_type="text",
                chunk_index=0,
                page_number=1,
                embedding=v_low,
            )
            session.add_all([doc, c])
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/rag/query",
                json={
                    "query": "Completely unmatched query with high threshold",
                    "top_k": 5,
                    "min_similarity": 0.99,
                    "document_id": str(doc_id),
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["grounded"] is False
            assert data["retrieved_chunks"] == 0
            assert data["citations"] == []
            assert "could not find enough relevant information" in data["answer"]

        app.dependency_overrides.pop(get_db, None)

        # Cleanup
        async with db_session_factory() as session:
            doc_obj = await session.get(Document, doc_id)
            if doc_obj:
                await session.delete(doc_obj)
                await session.commit()

    async def test_30_api_validation_errors(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Empty query
            res1 = await client.post("/api/v1/rag/query", json={"query": "", "top_k": 5})
            assert res1.status_code in (400, 422)

            # top_k out of bounds
            res2 = await client.post("/api/v1/rag/query", json={"query": "Valid", "top_k": 50})
            assert res2.status_code in (400, 422)

            # min_similarity out of bounds
            res3 = await client.post("/api/v1/rag/query", json={"query": "Valid", "min_similarity": 2.0})
            assert res3.status_code in (400, 422)
