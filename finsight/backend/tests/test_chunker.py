"""Unit and database integration test suite for TableAwareChunkerService (Sprint 5.1)."""

import json
import uuid
import pytest
from app.models.document import Document
from app.models.chunk import Chunk
from app.core.database import async_session
from app.services.pdf_parser import ParsedPage, ParsedDocument
from app.services.table_extractor import ExtractedTable
from app.services.table_semantics import FinancialTableSemantics, StatementType, PeriodType
from app.services.chunker import TableAwareChunkerService, ChunkData
from app.tasks.definitions import process_document


@pytest.fixture
def chunker():
    return TableAwareChunkerService(chunk_size=500, chunk_overlap=50)


def create_sample_table(
    table_id: str = "tbl_1_1",
    page_number: int = 1,
    statement_type: str = StatementType.INCOME_STATEMENT,
) -> ExtractedTable:
    return ExtractedTable(
        table_id=table_id,
        document_id="test_doc",
        page_number=page_number,
        headers=["Item", "2025", "2024"],
        rows=[
            ["Revenue", "$1,000", "$900"],
            ["Net Income", "$200", "$180"],
        ],
        column_count=3,
        row_count=3,
        title="Consolidated Statements of Operations",
        currency="USD",
        units="millions",
        markdown="| Item | 2025 | 2024 |\n| --- | --- | --- |\n| Revenue | $1,000 | $900 |\n| Net Income | $200 | $180 |",
        semantics=FinancialTableSemantics(
            statement_type=statement_type,
            confidence=0.95,
            period_type=PeriodType.ANNUAL,
            fiscal_periods=["2025", "2024"],
            currency="USD",
            units="millions",
            key_metrics=["revenue", "net_income"],
        ),
    )


class TestTableAwareChunkerService:

    def test_01_basic_text_chunking(self, chunker):
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=1,
            pages=[
                ParsedPage(
                    page_number=1,
                    text="This is a simple short paragraph for document chunking tests.",
                    char_count=62,
                    is_empty=False,
                )
            ],
        )
        chunks = chunker.create_chunks(doc)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "text"
        assert chunks[0].page_number == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].content == "This is a simple short paragraph for document chunking tests."

    def test_02_chunk_size_and_overlap_limits(self):
        small_chunker = TableAwareChunkerService(chunk_size=100, chunk_overlap=20)
        long_text = "Word " * 50  # 250 characters
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=1,
            pages=[ParsedPage(page_number=1, text=long_text, char_count=len(long_text), is_empty=False)],
        )
        chunks = small_chunker.create_chunks(doc)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.content) <= 120  # bounded near chunk_size

    def test_03_paragraph_and_sentence_boundaries(self, chunker):
        p1 = "First paragraph containing important narrative about revenue and operations."
        p2 = "Second paragraph discussing capital expenditure and strategic investments in 2025."
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=1,
            pages=[ParsedPage(page_number=1, text=f"{p1}\n\n{p2}", char_count=len(p1) + len(p2) + 2, is_empty=False)],
        )
        chunks = chunker.create_chunks(doc)
        assert len(chunks) >= 1
        # Checks that paragraph content is preserved
        combined = " ".join(c.content for c in chunks)
        assert "First paragraph" in combined
        assert "Second paragraph" in combined

    def test_04_page_boundary_preservation(self, chunker):
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=3,
            pages=[
                ParsedPage(page_number=1, text="Page 1 narrative content.", char_count=24, is_empty=False),
                ParsedPage(page_number=2, text="Page 2 narrative content.", char_count=24, is_empty=False),
                ParsedPage(page_number=3, text="Page 3 narrative content.", char_count=24, is_empty=False),
            ],
        )
        chunks = chunker.create_chunks(doc)
        assert len(chunks) == 3
        assert [c.page_number for c in chunks] == [1, 2, 3]
        assert [c.chunk_index for c in chunks] == [0, 1, 2]

    def test_05_table_chunk_creation_and_markdown(self, chunker):
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=1,
            pages=[ParsedPage(page_number=1, text="", char_count=0, is_empty=True)],
        )
        table = create_sample_table()
        chunks = chunker.create_chunks(doc, tables=[table])
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "table"
        assert chunks[0].page_number == 1
        assert chunks[0].content == table.markdown
        assert "| Revenue | $1,000 |" in chunks[0].content

    def test_06_table_semantic_metadata_preservation(self, chunker):
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=1,
            pages=[ParsedPage(page_number=1, text="", char_count=0, is_empty=True)],
        )
        table = create_sample_table()
        chunks = chunker.create_chunks(doc, tables=[table])
        meta = chunks[0].metadata
        assert meta["source_type"] == "table"
        assert meta["table_id"] == "tbl_1_1"
        assert meta["statement_type"] == "income_statement"
        assert meta["confidence"] == 0.95
        assert meta["period_type"] == "annual"
        assert meta["fiscal_periods"] == ["2025", "2024"]
        assert meta["currency"] == "USD"
        assert meta["units"] == "millions"
        assert "revenue" in meta["key_metrics"]

    def test_07_multiple_tables_on_page(self, chunker):
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=1,
            pages=[ParsedPage(page_number=1, text="Page 1 narrative.", char_count=17, is_empty=False)],
        )
        t1 = create_sample_table("tbl_1_1", 1, StatementType.INCOME_STATEMENT)
        t2 = create_sample_table("tbl_1_2", 1, StatementType.BALANCE_SHEET)
        chunks = chunker.create_chunks(doc, tables=[t1, t2])
        assert len(chunks) == 3  # 1 text + 2 tables
        assert chunks[0].chunk_type == "text"
        assert chunks[1].chunk_type == "table"
        assert chunks[2].chunk_type == "table"
        assert [c.chunk_index for c in chunks] == [0, 1, 2]

    def test_08_deterministic_chunk_indexes(self, chunker):
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=2,
            pages=[
                ParsedPage(page_number=1, text="Page 1 text.", char_count=12, is_empty=False),
                ParsedPage(page_number=2, text="Page 2 text.", char_count=12, is_empty=False),
            ],
        )
        t1 = create_sample_table("tbl_1_1", 1)
        t2 = create_sample_table("tbl_2_1", 2)
        chunks = chunker.create_chunks(doc, tables=[t1, t2])
        assert len(chunks) == 4
        assert [c.chunk_index for c in chunks] == [0, 1, 2, 3]
        assert [c.chunk_type for c in chunks] == ["text", "table", "text", "table"]

    def test_09_txt_document_chunking(self, chunker):
        doc = ParsedDocument(
            document_id="doc_txt",
            filename="notes.txt",
            total_pages=1,
            metadata={"format": "txt"},
            pages=[
                ParsedPage(
                    page_number=1,
                    text="Plain text file notes for financial analysis.\nSecond line of notes.",
                    char_count=67,
                    is_empty=False,
                )
            ],
        )
        chunks = chunker.create_chunks(doc)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "text"
        assert chunks[0].page_number == 1
        assert "Plain text file" in chunks[0].content

    def test_10_csv_structured_chunking(self, chunker):
        csv_text = "Metric,2024,2025\nRevenue,1000,1200\nNetIncome,200,250"
        doc = ParsedDocument(
            document_id="doc_csv",
            filename="metrics.csv",
            total_pages=1,
            metadata={"format": "csv"},
            pages=[
                ParsedPage(
                    page_number=1,
                    text=csv_text,
                    char_count=len(csv_text),
                    is_empty=False,
                    metadata={"format": "csv", "row_count": 3},
                )
            ],
        )
        chunks = chunker.create_chunks(doc)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "table"
        assert chunks[0].page_number == 1
        assert chunks[0].content == csv_text
        assert chunks[0].metadata["format"] == "csv"

    def test_11_large_csv_header_repetition(self):
        small_chunker = TableAwareChunkerService(chunk_size=100)
        lines = ["Metric,2024,2025"] + [f"MetricRow{i},100{i},200{i}" for i in range(10)]
        csv_text = "\n".join(lines)
        doc = ParsedDocument(
            document_id="doc_csv_large",
            filename="large_metrics.csv",
            total_pages=1,
            metadata={"format": "csv"},
            pages=[ParsedPage(page_number=1, text=csv_text, char_count=len(csv_text), is_empty=False)],
        )
        chunks = small_chunker.create_chunks(doc)
        assert len(chunks) > 1
        # Verify header is repeated on subsequent chunks
        for c in chunks:
            assert c.content.startswith("Metric,2024,2025")
            assert c.chunk_type == "table"

    def test_12_empty_page_handling_zero_chunks(self, chunker):
        doc = ParsedDocument(
            document_id="doc_empty",
            filename="empty_pages.pdf",
            total_pages=2,
            pages=[
                ParsedPage(page_number=1, text="   ", char_count=0, is_empty=True),
                ParsedPage(page_number=2, text="", char_count=0, is_empty=True),
            ],
        )
        chunks = chunker.create_chunks(doc)
        assert len(chunks) == 0  # Empty pages produce 0 chunks

    def test_13_json_serialization_safety(self, chunker):
        doc = ParsedDocument(
            document_id="doc1",
            filename="sample.pdf",
            total_pages=1,
            pages=[ParsedPage(page_number=1, text="Text", char_count=4, is_empty=False)],
        )
        table = create_sample_table()
        chunks = chunker.create_chunks(doc, tables=[table])
        for c in chunks:
            # Must serialize to JSON without throwing TypeError
            serialized = json.dumps(c.metadata)
            assert isinstance(serialized, str)


@pytest.mark.asyncio
class TestChunkDatabasePersistence:

    async def test_14_database_persistence_integration(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(
                id=doc_id,
                filename="persist_test.pdf",
                file_type="pdf",
                file_size=1024,
                status="pending",
            )
            session.add(doc)
            await session.commit()

        # Create mock chunk data
        chunker = TableAwareChunkerService()
        parsed_doc = ParsedDocument(
            document_id=str(doc_id),
            filename="persist_test.pdf",
            total_pages=1,
            pages=[ParsedPage(page_number=1, text="Persisted financial text.", char_count=25, is_empty=False)],
        )
        table = create_sample_table()
        chunks = chunker.create_chunks(parsed_doc, [table])

        # Persist chunks inside transaction
        async with db_session_factory() as session:
            for c in chunks:
                db_chunk = Chunk(
                    document_id=doc_id,
                    content=c.content,
                    chunk_type=c.chunk_type,
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    metadata_=c.metadata,
                    embedding=None,
                )
                session.add(db_chunk)
            await session.commit()

        # Verify chunks persisted in database
        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            db_chunks = res.scalars().all()
            assert len(db_chunks) == 2
            assert all(c.embedding is None for c in db_chunks)
            types = {c.chunk_type for c in db_chunks}
            assert "text" in types
            assert "table" in types

            # Cleanup
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()

    async def test_15_embedding_is_null_verification(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="null_embed.pdf", file_type="pdf", file_size=500, status="pending")
            session.add(doc)
            chunk = Chunk(
                document_id=doc_id,
                content="Chunk content without embeddings.",
                chunk_type="text",
                chunk_index=0,
                page_number=1,
                embedding=None,
            )
            session.add(chunk)
            await session.commit()

        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            retrieved = res.scalar_one()
            assert retrieved.embedding is None

            # Cleanup
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()

    async def test_16_idempotent_reprocessing_chunk_replacement(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="reprocess.pdf", file_type="pdf", file_size=500, status="pending")
            session.add(doc)
            # Add 2 initial chunks
            c1 = Chunk(document_id=doc_id, content="Old 1", chunk_type="text", chunk_index=0, page_number=1)
            c2 = Chunk(document_id=doc_id, content="Old 2", chunk_type="text", chunk_index=1, page_number=1)
            session.add_all([c1, c2])
            await session.commit()

        # Reprocess: delete old chunks and add 1 new chunk in atomic transaction
        async with db_session_factory() as session:
            from sqlalchemy import delete, select
            await session.execute(delete(Chunk).where(Chunk.document_id == doc_id))
            new_chunk = Chunk(document_id=doc_id, content="New 1", chunk_type="text", chunk_index=0, page_number=1)
            session.add(new_chunk)
            await session.commit()

        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            current_chunks = res.scalars().all()
            assert len(current_chunks) == 1
            assert current_chunks[0].content == "New 1"

            # Cleanup
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()

    async def test_17_document_total_chunks_update(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="counter_test.pdf", file_type="pdf", file_size=500, status="pending")
            session.add(doc)
            await session.commit()

        chunker = TableAwareChunkerService()
        parsed_doc = ParsedDocument(
            document_id=str(doc_id),
            filename="counter_test.pdf",
            total_pages=2,
            pages=[
                ParsedPage(page_number=1, text="Page 1 text.", char_count=12, is_empty=False),
                ParsedPage(page_number=2, text="Page 2 text.", char_count=12, is_empty=False),
            ],
        )
        chunks = chunker.create_chunks(parsed_doc)

        async with db_session_factory() as session:
            from sqlalchemy import select
            for c in chunks:
                session.add(
                    Chunk(
                        document_id=doc_id,
                        content=c.content,
                        chunk_type=c.chunk_type,
                        chunk_index=c.chunk_index,
                        page_number=c.page_number,
                        metadata_=c.metadata,
                    )
                )
            result = await session.execute(select(Document).where(Document.id == doc_id))
            doc_to_update = result.scalar_one()
            doc_to_update.total_chunks = len(chunks)
            await session.commit()

        async with db_session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(Document).where(Document.id == doc_id))
            retrieved_doc = result.scalar_one()
            assert retrieved_doc.total_chunks == 2

            # Cleanup
            await session.delete(retrieved_doc)
            await session.commit()

    async def test_18_transactional_rollback_on_failure(self, db_session_factory):
        doc_id = uuid.uuid4()
        async with db_session_factory() as session:
            doc = Document(id=doc_id, filename="rollback_test.pdf", file_type="pdf", file_size=500, status="pending")
            session.add(doc)
            await session.commit()

        # Simulate failed transaction
        try:
            async with db_session_factory() as session:
                c1 = Chunk(document_id=doc_id, content="Valid chunk", chunk_type="text", chunk_index=0, page_number=1)
                session.add(c1)
                # Intentional error to trigger rollback
                raise RuntimeError("Simulated failure during chunk insertion")
        except RuntimeError:
            pass

        # Verify no chunks were persisted due to rollback
        async with db_session_factory() as session:
            from sqlalchemy import select
            res = await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
            assert len(res.scalars().all()) == 0

            # Cleanup
            doc_to_delete = await session.get(Document, doc_id)
            if doc_to_delete:
                await session.delete(doc_to_delete)
                await session.commit()
