import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models.user import User, UserSession
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.conversation import ConversationSession, ConversationMessage
from app.models.report import Report
from app.services.retrieval_service import RetrievalService
from app.services.rag_service import RAGService
from app.services.embedding_service import EmbeddingService
from app.api.deps import get_current_user

settings = get_settings()


@pytest.mark.asyncio
class TestAuthorizationAndTenantIsolation:

    async def _setup_users_and_resources(self, db_session_factory):
        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()

        user_a = User(
            id=user_a_id,
            email=f"user_a_{user_a_id.hex[:8]}@example.com",
            name="User Alpha",
            provider="google",
            provider_sub=f"google-sub-{user_a_id.hex}",
            is_active=True,
        )
        user_b = User(
            id=user_b_id,
            email=f"user_b_{user_b_id.hex[:8]}@example.com",
            name="User Beta",
            provider="google",
            provider_sub=f"google-sub-{user_b_id.hex}",
            is_active=True,
        )

        doc_a_id = uuid.uuid4()
        doc_b_id = uuid.uuid4()

        doc_a = Document(
            id=doc_a_id,
            user_id=user_a_id,
            filename="apple_q1.pdf",
            file_type="pdf",
            file_size=1024,
            title="Apple Q1 Results",
            status="indexed",
            total_chunks=1,
        )
        doc_b = Document(
            id=doc_b_id,
            user_id=user_b_id,
            filename="microsoft_q1.pdf",
            file_type="pdf",
            file_size=2048,
            title="Microsoft Q1 Results",
            status="indexed",
            total_chunks=1,
        )

        chunk_a = Chunk(
            id=uuid.uuid4(),
            document_id=doc_a_id,
            content="Apple Q1 net income was $30 billion. Confidential Project Titan.",
            chunk_type="text",
            chunk_index=0,
            page_number=1,
            embedding=[0.5] * 1536,
        )
        chunk_b = Chunk(
            id=uuid.uuid4(),
            document_id=doc_b_id,
            content="Microsoft Q1 cloud revenue grew by 25 percent. Azure dominance.",
            chunk_type="text",
            chunk_index=0,
            page_number=1,
            embedding=[0.5] * 1536,
        )

        conv_a_id = uuid.uuid4()
        conv_b_id = uuid.uuid4()

        conv_a = ConversationSession(
            id=conv_a_id,
            user_id=user_a_id,
            title="Apple Analysis Session",
        )
        conv_b = ConversationSession(
            id=conv_b_id,
            user_id=user_b_id,
            title="Microsoft Analysis Session",
        )

        msg_a = ConversationMessage(
            id=uuid.uuid4(),
            session_id=conv_a_id,
            role="user",
            content="How was Apple's Q1 margin?",
        )
        msg_b = ConversationMessage(
            id=uuid.uuid4(),
            session_id=conv_b_id,
            role="user",
            content="What was Microsoft's cloud growth?",
        )

        report_a_id = uuid.uuid4()
        report_b_id = uuid.uuid4()

        report_a = Report(
            id=report_a_id,
            user_id=user_a_id,
            title="Apple Investment Memo",
            query="Analyze Apple financial performance",
            status="completed",
            document_ids=[str(doc_a_id)],
            content="Apple valuation analysis memo.",
        )
        report_b = Report(
            id=report_b_id,
            user_id=user_b_id,
            title="Microsoft Investment Memo",
            query="Analyze Microsoft cloud growth",
            status="completed",
            document_ids=[str(doc_b_id)],
            content="Microsoft valuation analysis memo.",
        )

        async with db_session_factory() as session:
            session.add_all([user_a, user_b])
            await session.commit()

        async with db_session_factory() as session:
            session.add_all([doc_a, doc_b, conv_a, conv_b, report_a, report_b])
            await session.commit()

        async with db_session_factory() as session:
            session.add_all([chunk_a, chunk_b, msg_a, msg_b])
            await session.commit()

        return {
            "user_a": user_a,
            "user_b": user_b,
            "doc_a": doc_a,
            "doc_b": doc_b,
            "chunk_a": chunk_a,
            "chunk_b": chunk_b,
            "conv_a": conv_a,
            "conv_b": conv_b,
            "report_a": report_a,
            "report_b": report_b,
        }

    async def _cleanup(self, db_session_factory, data):
        async with db_session_factory() as session:
            for r in (data["report_a"], data["report_b"]):
                obj = await session.get(Report, r.id)
                if obj:
                    await session.delete(obj)
            for c in (data["conv_a"], data["conv_b"]):
                obj = await session.get(ConversationSession, c.id)
                if obj:
                    await session.delete(obj)
            for d in (data["doc_a"], data["doc_b"]):
                obj = await session.get(Document, d.id)
                if obj:
                    await session.delete(obj)
            for u in (data["user_a"], data["user_b"]):
                obj = await session.get(User, u.id)
                if obj:
                    await session.delete(obj)
            await session.commit()

    async def test_document_cross_user_isolation(self, db_session_factory):
        """Verify User A cannot retrieve, delete, or inspect User B's documents/chunks."""
        data = await self._setup_users_and_resources(db_session_factory)
        try:
            user_a = data["user_a"]
            user_b = data["user_b"]
            doc_a = data["doc_a"]
            doc_b = data["doc_b"]
            chunk_a = data["chunk_a"]
            chunk_b = data["chunk_b"]

            transport = ASGITransport(app=app)

            # 1. User A accesses own resources -> OK
            app.dependency_overrides[get_current_user] = lambda: user_a
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                r_a = await ac.get(f"/api/v1/documents/{doc_a.id}")
                assert r_a.status_code == 200
                assert r_a.json()["title"] == "Apple Q1 Results"

                r_chunk_a = await ac.get(f"/api/v1/documents/chunks/{chunk_a.id}")
                assert r_chunk_a.status_code == 200

                # User A accesses User B resources -> 404 Not Found (IDOR prevention)
                r_idor = await ac.get(f"/api/v1/documents/{doc_b.id}")
                assert r_idor.status_code == 404

                r_chunk_idor = await ac.get(f"/api/v1/documents/chunks/{chunk_b.id}")
                assert r_chunk_idor.status_code == 404

                # User A document list -> only doc_a
                r_list = await ac.get("/api/v1/documents/")
                assert r_list.status_code == 200
                doc_ids = [d["id"] for d in r_list.json()["documents"]]
                assert str(doc_a.id) in doc_ids
                assert str(doc_b.id) not in doc_ids

                # User A delete User B document -> 404
                r_del = await ac.delete(f"/api/v1/documents/{doc_b.id}")
                assert r_del.status_code == 404

            # 2. Symmetric isolation for User B
            app.dependency_overrides[get_current_user] = lambda: user_b
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                r_b = await ac.get(f"/api/v1/documents/{doc_b.id}")
                assert r_b.status_code == 200

                r_idor_b = await ac.get(f"/api/v1/documents/{doc_a.id}")
                assert r_idor_b.status_code == 404

                r_del_b = await ac.delete(f"/api/v1/documents/{doc_a.id}")
                assert r_del_b.status_code == 404
        finally:
            await self._cleanup(db_session_factory, data)

    async def test_conversation_cross_user_isolation(self, db_session_factory):
        """Verify User A cannot retrieve or delete User B's conversation sessions."""
        data = await self._setup_users_and_resources(db_session_factory)
        try:
            user_a = data["user_a"]
            user_b = data["user_b"]
            conv_a = data["conv_a"]
            conv_b = data["conv_b"]

            transport = ASGITransport(app=app)

            # User A
            app.dependency_overrides[get_current_user] = lambda: user_a
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                r_a = await ac.get(f"/api/v1/conversations/{conv_a.id}")
                assert r_a.status_code == 200
                assert r_a.json()["title"] == "Apple Analysis Session"

                # IDOR attempt
                r_idor = await ac.get(f"/api/v1/conversations/{conv_b.id}")
                assert r_idor.status_code == 404

                # Delete User B conversation -> 404 Not Found
                r_del = await ac.delete(f"/api/v1/conversations/{conv_b.id}")
                assert r_del.status_code == 404
        finally:
            await self._cleanup(db_session_factory, data)

    async def test_report_cross_user_isolation(self, db_session_factory):
        """Verify User A cannot access User B's reports or reference User B's documents."""
        data = await self._setup_users_and_resources(db_session_factory)
        try:
            user_a = data["user_a"]
            user_b = data["user_b"]
            doc_b = data["doc_b"]
            report_a = data["report_a"]
            report_b = data["report_b"]

            transport = ASGITransport(app=app)

            # User A
            app.dependency_overrides[get_current_user] = lambda: user_a
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                r_a = await ac.get(f"/api/v1/reports/{report_a.id}")
                assert r_a.status_code == 200
                assert r_a.json()["title"] == "Apple Investment Memo"

                # IDOR attempt
                r_idor = await ac.get(f"/api/v1/reports/{report_b.id}")
                assert r_idor.status_code == 404

                # List reports
                r_list = await ac.get("/api/v1/reports")
                assert r_list.status_code == 200
                rep_ids = [r["id"] for r in r_list.json()["reports"]]
                assert str(report_a.id) in rep_ids
                assert str(report_b.id) not in rep_ids

                # Attempt to create report referencing User B's document
                payload = {
                    "title": "Cross Tenant Malicious Report",
                    "query": "What are Microsoft's confidential cloud metrics?",
                    "document_ids": [str(doc_b.id)],
                }
                r_create = await ac.post("/api/v1/reports", json=payload)
                assert r_create.status_code == 404
        finally:
            await self._cleanup(db_session_factory, data)

    async def test_vector_pgvector_search_tenant_isolation(self, db_session_factory):
        """
        CRITICAL VECTOR ISOLATION TEST:
        Verify pgvector similarity search strictly constrains results to the querying user's documents.
        User A search must NEVER return User B chunks, even with identical vector query embeddings.
        """
        data = await self._setup_users_and_resources(db_session_factory)
        try:
            user_a = data["user_a"]
            user_b = data["user_b"]
            doc_a = data["doc_a"]
            doc_b = data["doc_b"]

            class FakeSearchEmbeddingService:
                async def embed_query(self, query: str) -> list[float]:
                    return [0.5] * 1536
                async def close(self):
                    pass

            service = RetrievalService(
                embedding_service=FakeSearchEmbeddingService(),
                session_factory=db_session_factory,
            )

            # 1. User A search
            results_a = await service.search(
                query="What is the confidential revenue project?",
                top_k=10,
                user_id=user_a.id,
            )
            assert len(results_a) > 0
            for chunk in results_a:
                assert chunk.document_id == doc_a.id
                assert "Titan" in chunk.content
                assert "Azure" not in chunk.content

            # 2. User B search
            results_b = await service.search(
                query="What is the confidential revenue project?",
                top_k=10,
                user_id=user_b.id,
            )
            assert len(results_b) > 0
            for chunk in results_b:
                assert chunk.document_id == doc_b.id
                assert "Azure" in chunk.content
                assert "Titan" not in chunk.content
        finally:
            await self._cleanup(db_session_factory, data)

    async def test_rag_service_tenant_isolation(self, db_session_factory):
        """
        Verify RAG grounded answering passes user_id to the retrieval boundary,
        ensuring generated answers and citations strictly come from caller's tenant.
        """
        data = await self._setup_users_and_resources(db_session_factory)
        try:
            user_a = data["user_a"]
            doc_a = data["doc_a"]

            class FakeSearchEmbeddingService:
                async def embed_query(self, query: str) -> list[float]:
                    return [0.5] * 1536
                async def close(self):
                    pass

            retrieval_service = RetrievalService(
                embedding_service=FakeSearchEmbeddingService(),
                session_factory=db_session_factory,
            )

            class MockLLMGenerationService:
                async def generate_answer(self, query: str, context: str) -> str:
                    return f"Generated answer: {context[:40]} [SOURCE 1]"
                async def close(self):
                    pass

            rag = RAGService(
                retrieval_service=retrieval_service,
                generation_service=MockLLMGenerationService(),
            )

            # User A RAG query
            ans_a = await rag.answer("What was the confidential project?", user_id=user_a.id)
            assert len(ans_a.citations) > 0
            for cit in ans_a.citations:
                assert cit.document_id == doc_a.id
        finally:
            await self._cleanup(db_session_factory, data)
