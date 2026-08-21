"""Comprehensive test suite for Conversation Sessions & Multi-Turn RAG (Sprint 8.2)."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import ValidationError, NotFoundError, ProcessingError
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.conversation import ConversationSession, ConversationMessage
from app.services.embedding_service import FakeGenAIClient, EmbeddingService
from app.services.retrieval_service import RetrievalService, RetrievalResult
from app.services.generation_service import GenerationService
from app.services.rag_service import RAGService, RAGResponse, SourceCitation
from app.services.query_context_service import QueryContextService
from app.services.conversation_service import ConversationService
from app.main import app

settings = get_settings()


class MockRAGService:
    def __init__(self, return_answer: str = "Mocked answer [SOURCE 1]", raise_error: Exception | None = None):
        self.return_answer = return_answer
        self.raise_error = raise_error
        self.called_query = None
        self.called_top_k = None
        self.called_min_sim = None
        self.called_doc_id = None
        self.generation_service = FakeGenService()
        self.retrieval_service = FakeRetService()

    async def answer(self, query: str, top_k: int = 5, min_similarity: float = 0.3, document_id=None, db=None) -> RAGResponse:
        self.called_query = query
        self.called_top_k = top_k
        self.called_min_sim = min_similarity
        self.called_doc_id = document_id
        if self.raise_error:
            raise self.raise_error

        cit = SourceCitation(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            page_number=1,
            chunk_type="table",
            similarity=0.92,
            statement_type="income_statement",
            fiscal_periods=["2025"],
        )
        return RAGResponse(
            query=query,
            answer=self.return_answer,
            citations=[cit],
            retrieved_chunks=1,
            grounded=True,
        )


class FakeGenService:
    async def generate_answer(self, query: str, context: str) -> str:
        return "Mocked answer [SOURCE 1]"

    async def close(self):
        pass


class FakeRetService:
    def __init__(self):
        self.embedding_service = FakeGenService()

    async def search(self, query: str, top_k: int = 5, min_similarity: float = 0.0, document_id=None, db=None) -> list[RetrievalResult]:
        from app.services.retrieval_service import RetrievalResult
        return [
            RetrievalResult(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Apple total revenue in 2025 was $1000 million. Total revenue in 2024 was $900 million.",
                chunk_type="table",
                chunk_index=0,
                page_number=1,
                similarity=0.92,
                metadata={"statement_type": "income_statement", "fiscal_periods": ["2025", "2024"]},
            )
        ]


@pytest.mark.asyncio
class TestConversationServiceUnit:

    async def test_01_create_session(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            res = await service.create_session(title="Apple 10-K Analysis", db=session)
            assert res.id is not None
            assert res.title == "Apple 10-K Analysis"
            assert res.message_count == 0

    async def test_02_get_session(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            created = await service.create_session(title="Session 2", db=session)
            fetched = await service.get_session(session_id=created.id, db=session)
            assert fetched.id == created.id
            assert fetched.title == "Session 2"

    async def test_03_delete_session(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            created = await service.create_session(title="To Delete", db=session)
            deleted = await service.delete_session(session_id=created.id, db=session)
            assert deleted is True

            with pytest.raises(NotFoundError):
                await service.get_session(session_id=created.id, db=session)

    async def test_04_add_user_message(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Chat", db=session)
            msg = await service.add_message(session_id=sess.id, role="user", content="What was revenue?", db=session)
            assert msg.id is not None
            assert msg.role == "user"
            assert msg.content == "What was revenue?"

    async def test_05_add_assistant_message(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Chat", db=session)
            msg = await service.add_message(session_id=sess.id, role="assistant", content="Revenue was $1000 [SOURCE 1]", db=session)
            assert msg.role == "assistant"
            assert "[SOURCE 1]" in msg.content

    async def test_06_get_messages_chronological(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Ordering", db=session)
            m1 = await service.add_message(session_id=sess.id, role="user", content="Msg 1", db=session)
            m2 = await service.add_message(session_id=sess.id, role="assistant", content="Msg 2", db=session)
            m3 = await service.add_message(session_id=sess.id, role="user", content="Msg 3", db=session)

            msgs = await service.get_recent_messages(session_id=sess.id, limit=10, db=session)
            assert len(msgs) == 3
            assert msgs[0].content == "Msg 1"
            assert msgs[1].content == "Msg 2"
            assert msgs[2].content == "Msg 3"

    async def test_07_history_limit(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Limit Test", db=session)
            for i in range(15):
                await service.add_message(session_id=sess.id, role="user", content=f"Msg {i}", db=session)

            msgs = await service.get_recent_messages(session_id=sess.id, limit=5, db=session)
            assert len(msgs) == 5
            # Should be the most recent 5 in chronological order: Msg 10, 11, 12, 13, 14
            assert msgs[0].content == "Msg 10"
            assert msgs[-1].content == "Msg 14"

    async def test_08_session_isolation(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            s1 = await service.create_session(title="S1", db=session)
            s2 = await service.create_session(title="S2", db=session)

            await service.add_message(session_id=s1.id, role="user", content="Secret S1 question", db=session)
            await service.add_message(session_id=s2.id, role="user", content="Secret S2 question", db=session)

            m_s1 = await service.get_recent_messages(session_id=s1.id, db=session)
            m_s2 = await service.get_recent_messages(session_id=s2.id, db=session)

            assert len(m_s1) == 1
            assert m_s1[0].content == "Secret S1 question"
            assert len(m_s2) == 1
            assert m_s2[0].content == "Secret S2 question"

    async def test_09_empty_query_rejected(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Empty Query", db=session)
            with pytest.raises(ValidationError):
                await service.process_query(session_id=sess.id, query="", db=session)

    async def test_10_whitespace_query_rejected(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Whitespace", db=session)
            with pytest.raises(ValidationError):
                await service.process_query(session_id=sess.id, query="   \t\n  ", db=session)

    async def test_11_query_length_validation(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Too Long", db=session)
            long_query = "A" * (settings.CONVERSATION_MAX_MESSAGE_CHARS + 50)
            with pytest.raises(ValidationError):
                await service.process_query(session_id=sess.id, query=long_query, db=session)

    async def test_12_invalid_session(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            with pytest.raises(NotFoundError):
                await service.process_query(session_id=uuid.uuid4(), query="Valid query", db=session)

    def test_13_followup_question_detection(self):
        assert QueryContextService.is_followup_query("What about 2024?") is True
        assert QueryContextService.is_followup_query("And how about operating income?") is True
        assert QueryContextService.is_followup_query("How much did it change?") is True
        assert QueryContextService.is_followup_query("2024?") is True
        assert QueryContextService.is_followup_query("What was Apple's total revenue in 2025?") is False

    def test_14_followup_query_resolution(self):
        prev = [
            ConversationMessage(
                id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                role="user",
                content="What was Apple's revenue in 2025?",
            ),
            ConversationMessage(
                id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                role="assistant",
                content="Apple reported $1,000 million [SOURCE 1].",
            ),
        ]
        resolved = QueryContextService.resolve_retrieval_query("What about 2024?", prev)
        assert "Apple" in resolved
        assert "revenue" in resolved
        assert "2024" in resolved
        assert "2025" not in resolved

    async def test_15_context_does_not_include_unrelated_session(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            s_other = await service.create_session(title="Other", db=session)
            await service.add_message(session_id=s_other.id, role="user", content="Tesla gross margin 2023", db=session)

            s_current = await service.create_session(title="Current", db=session)
            history = await service.get_recent_messages(session_id=s_current.id, db=session)
            assert len(history) == 0

    async def test_16_retrieval_uses_rewritten_query(self, db_session_factory):
        async with db_session_factory() as session:
            mock_rag = MockRAGService()
            service = ConversationService(rag_service=mock_rag)
            sess = await service.create_session(title="Rewrite Test", db=session)

            # Turn 1
            await service.process_query(session_id=sess.id, query="What was Apple's revenue in 2025?", db=session)

            # Turn 2 (Follow-up)
            resp = await service.process_query(session_id=sess.id, query="What about 2024?", db=session)
            assert resp.query == "What about 2024?"
            assert resp.resolved_query is not None
            assert "2024" in resp.resolved_query
            assert mock_rag.called_query == resp.resolved_query

    async def test_17_original_question_preserved(self, db_session_factory):
        async with db_session_factory() as session:
            mock_rag = MockRAGService()
            service = ConversationService(rag_service=mock_rag)
            sess = await service.create_session(title="Original Query Preservation", db=session)

            resp = await service.process_query(session_id=sess.id, query="What was Apple revenue?", db=session)
            assert resp.query == "What was Apple revenue?"

    async def test_18_conversation_not_used_as_citation(self, db_session_factory):
        async with db_session_factory() as session:
            mock_rag = MockRAGService(return_answer="Apple revenue was $1,000 [SOURCE 1]")
            service = ConversationService(rag_service=mock_rag)
            sess = await service.create_session(title="Citation Authority", db=session)

            resp = await service.process_query(session_id=sess.id, query="Turn 1", db=session)
            for c in resp.citations:
                assert c.chunk_id is not None
                assert c.chunk_type in ("text", "table")

    async def test_19_retrieved_sources_remain_authoritative(self, db_session_factory):
        async with db_session_factory() as session:
            mock_rag = MockRAGService(return_answer="Income Statement shows $400 gross profit [SOURCE 1]")
            service = ConversationService(rag_service=mock_rag)
            sess = await service.create_session(title="Authority", db=session)

            resp = await service.process_query(session_id=sess.id, query="Gross profit?", db=session)
            assert resp.grounded is True
            assert len(resp.citations) == 1

    async def test_20_user_message_persisted(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService(rag_service=MockRAGService())
            sess = await service.create_session(title="Persist User", db=session)

            await service.process_query(session_id=sess.id, query="Query to persist", db=session)
            msgs = await service.get_recent_messages(session_id=sess.id, db=session)
            assert any(m.role == "user" and m.content == "Query to persist" for m in msgs)

    async def test_21_assistant_message_persisted(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService(rag_service=MockRAGService(return_answer="Assistant Answer 123"))
            sess = await service.create_session(title="Persist Assistant", db=session)

            await service.process_query(session_id=sess.id, query="Hello", db=session)
            msgs = await service.get_recent_messages(session_id=sess.id, db=session)
            assert any(m.role == "assistant" and m.content == "Assistant Answer 123" for m in msgs)

    async def test_22_generation_failure_preserves_user_message(self, db_session_factory):
        async with db_session_factory() as session:
            failing_rag = MockRAGService(raise_error=ProcessingError(message="API Quota Exceeded"))
            service = ConversationService(rag_service=failing_rag)
            sess = await service.create_session(title="Failure Safety", db=session)

            with pytest.raises(ProcessingError):
                await service.process_query(session_id=sess.id, query="Query that fails in RAG", db=session)

            # User query must still be persisted in the session
            msgs = await service.get_recent_messages(session_id=sess.id, db=session)
            assert len(msgs) == 1
            assert msgs[0].role == "user"
            assert msgs[0].content == "Query that fails in RAG"

    async def test_23_session_delete_cascades_messages(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Cascade Delete", db=session)
            await service.add_message(session_id=sess.id, role="user", content="Msg", db=session)

            await service.delete_session(session_id=sess.id, db=session)

            # Direct check on messages table
            stmt = select(ConversationMessage).where(ConversationMessage.session_id == sess.id)
            res = await session.execute(stmt)
            assert len(res.scalars().all()) == 0

    async def test_24_existing_rag_endpoint_regression(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Single-turn RAG must reject invalid query and remain functional
            res = await client.post("/api/v1/rag/query", json={"query": "", "top_k": 5})
            assert res.status_code in (400, 422)

    async def test_25_existing_search_endpoint_regression(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/v1/search", json={"query": "", "top_k": 5})
            assert res.status_code in (400, 422)

    async def test_26_max_session_messages(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Max Messages", db=session)
            for i in range(12):
                await service.add_message(session_id=sess.id, role="user", content=f"M {i}", db=session)
            msgs = await service.get_recent_messages(session_id=sess.id, limit=settings.CONVERSATION_MAX_HISTORY_MESSAGES, db=session)
            assert len(msgs) == settings.CONVERSATION_MAX_HISTORY_MESSAGES

    async def test_27_top_k_validation(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="TopK", db=session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(f"/api/v1/conversations/{sess.id}/query", json={"query": "Valid", "top_k": 0})
                assert res.status_code in (400, 422)

    async def test_28_similarity_validation(self, db_session_factory):
        async with db_session_factory() as session:
            sess = (await ConversationService().create_session(title="Sim", db=session)).id
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(f"/api/v1/conversations/{sess}/query", json={"query": "Valid", "min_similarity": 1.5})
                assert res.status_code in (400, 422)

    def test_29_deterministic_followup_resolution(self):
        msgs = [
            ConversationMessage(id=uuid.uuid4(), session_id=uuid.uuid4(), role="user", content="Consolidated revenue 2025?"),
        ]
        res1 = QueryContextService.resolve_retrieval_query("What about 2024?", msgs)
        res2 = QueryContextService.resolve_retrieval_query("What about 2024?", msgs)
        assert res1 == res2
        assert "2024" in res1

    async def test_30_no_secret_leakage(self, db_session_factory):
        async with db_session_factory() as session:
            service = ConversationService()
            sess = await service.create_session(title="Secret Test", db=session)
            try:
                await service.process_query(session_id=sess.id, query="", db=session)
            except ValidationError as exc:
                assert settings.GEMINI_API_KEY not in str(exc)
                assert "api_key" not in str(exc).lower()
