# AI Agent Instructions for FinSight Development

This document provides clear instructions for AI coding assistants (ChatGPT, Claude, Cursor, etc.) to understand the FinSight project architecture, coding standards, and how to properly assist with development.

## 🎯 Project Overview

FinSight is an AI-powered investment research copilot that synthesizes insights from complex financial documents (10-Ks, earnings reports, etc.) using:

- **RAG (Retrieval Augmented Generation)** for grounded responses
- **Multi-agent orchestration** with LangGraph for complex reasoning
- **pgvector** for semantic search in PostgreSQL
- **Table-aware document parsing** for financial data extraction

### Core Philosophy
Act like a human financial analyst, not just a search engine. Synthesize insights across multiple documents with verifiable citations.

🏗️ Architecture Pattern
Layer Structure (Strict Separation)
text

┌─────────────────────────────────────────┐
│  API Routes (app/api/routes/)           │  ← HTTP endpoints only
│  - Receive requests                     │
│  - Validate input (Pydantic schemas)    │
│  - Call services                        │
│  - Return responses                     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Services (app/services/)               │  ← Business logic
│  - Orchestrate operations               │
│  - No HTTP knowledge                    │
│  - Use models + external APIs           │
│  - Transaction management               │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Models (app/models/)                   │  ← Database tables
│  - SQLAlchemy ORM models                │
│  - Relationships defined                │
│  - No business logic                    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Database (PostgreSQL + pgvector)       │  ← Data persistence
└─────────────────────────────────────────┘
Never violate layer boundaries. Routes don't touch models directly. Services don't return FastAPI responses.

📐 Coding Standards
1. Type Hints (MANDATORY)
Python

# ✅ CORRECT - Full type hints
async def get_document(self, document_id: uuid.UUID) -> Document | None:
    result = await self.db.execute(
        select(Document).where(Document.id == document_id)
    )
    return result.scalar_one_or_none()

# ❌ WRONG - No type hints
async def get_document(self, document_id):
    result = await self.db.execute(
        select(Document).where(Document.id == document_id)
    )
    return result.scalar_one_or_none()
Why: Type hints catch bugs before runtime and make code self-documenting.

2. Async/Await (MANDATORY for I/O)
Python

# ✅ CORRECT - Async file I/O
async with aiofiles.open(file_path, "wb") as f:
    await f.write(content)

# ❌ WRONG - Blocking I/O
with open(file_path, "wb") as f:
    f.write(content)
Why: Blocking I/O freezes the entire server. Async allows handling other requests during waits.

3. Dependency Injection
Python

# ✅ CORRECT - Service receives dependencies
class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

# Route injects dependency
@router.post("/upload")
async def upload(
    file: UploadFile,
    db: AsyncSession = Depends(get_db)  # FastAPI injects this
):
    service = DocumentService(db)
    return await service.upload_document(file)

# ❌ WRONG - Service creates its own dependencies
class DocumentService:
    def __init__(self):
        self.db = create_session()  # Hard-coded dependency
Why: Makes testing easier (inject mock database). Follows SOLID principles.

4. Error Handling
Python

# ✅ CORRECT - Specific HTTP exceptions
from fastapi import HTTPException, status

if not document:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document not found"
    )

# ❌ WRONG - Generic exceptions
if not document:
    raise Exception("Not found")
Why: FastAPI converts HTTPException to proper HTTP responses. Generic exceptions return 500 errors.

5. Pydantic Schemas vs SQLAlchemy Models
Python

# SQLAlchemy Model (app/models/document.py)
class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    # ... database structure

# Pydantic Schema (app/schemas/document.py)
class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    # ... API response shape
    
    class Config:
        from_attributes = True  # Allows: DocumentResponse.model_validate(db_document)
Rule:

Models = how data is STORED
Schemas = how data is SENT/RECEIVED via API
Never return SQLAlchemy models directly from API routes.

6. Configuration Management
Python

# ✅ CORRECT - Use settings
from app.core.config import get_settings

settings = get_settings()
max_size = settings.MAX_FILE_SIZE

# ❌ WRONG - Hardcoded values
max_size = 50 * 1024 * 1024
Why: Centralized config makes changes easy. Settings can be overridden via environment variables.

7. Database Queries (SQLAlchemy 2.0 Style)
Python

# ✅ CORRECT - Modern SQLAlchemy 2.0
from sqlalchemy import select

result = await db.execute(
    select(Document).where(Document.status == "pending")
)
documents = result.scalars().all()

# ❌ WRONG - Old style (pre-2.0)
documents = db.query(Document).filter(Document.status == "pending").all()
Why: SQLAlchemy 2.0 is async-first and more explicit.

8. Circular Import Prevention
Python

# ✅ CORRECT - TYPE_CHECKING guard
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.chunk import Chunk

class Document(Base):
    chunks: Mapped[list["Chunk"]] = relationship("Chunk", ...)  # String reference

# ❌ WRONG - Direct import causes circular dependency
from app.models.chunk import Chunk

class Document(Base):
    chunks: Mapped[list[Chunk]] = relationship(Chunk, ...)
Why: Models often reference each other. TYPE_CHECKING imports only run for editors, not at runtime.

🗂️ File Naming Conventions
text

✅ Snake_case for Python files:
   document_service.py
   embedding_service.py
   retriever_agent.py

✅ PascalCase for classes:
   class DocumentService
   class EmbeddingService
   
✅ lowercase for packages:
   app/services/
   app/models/
📦 When Adding New Dependencies
Always update requirements.txt:

Bash

# Add to requirements.txt
langchain==0.1.0
Then rebuild:

Bash

docker compose down
docker compose up -d --build
Pin exact versions (==0.1.0 not >=0.1.0) to avoid surprise breakages.

🧪 Testing Pattern (Future)
When writing tests:

Python

# Use pytest with async support
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_upload_document():
    async with AsyncClient(app=app, base_url="http://test") as client:
        files = {"file": ("test.pdf", b"fake pdf content")}
        response = await client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 201
Test structure:

tests/unit/ - Test individual functions
tests/integration/ - Test full API flows
tests/fixtures/ - Sample PDFs, test data
🔐 Security Rules
1. Never Commit Secrets
Bash

# ✅ In .env (not committed)
OPENAI_API_KEY=sk-real-key-here

# ✅ In .env.example (committed)
OPENAI_API_KEY=sk-your-key-here
2. Validate All Inputs
Python

# ✅ CORRECT
file_extension = file.filename.split(".")[-1].lower()
if file_extension not in settings.ALLOWED_FILE_TYPES:
    raise HTTPException(status_code=400, detail="Invalid file type")

# ❌ WRONG - Accepting any file
await file.save(file.filename)  # User could upload malicious file
3. Sanitize Filenames
Python

# ✅ CORRECT - Prefix with UUID
safe_filename = f"{document_id}_{file.filename}"

# ❌ WRONG - User controls full filename
file_path = f"storage/{file.filename}"  # User could upload "../../../etc/passwd"
🐳 Docker Best Practices
1. Multi-Stage Builds (Future Optimization)
Dockerfile

# Production Dockerfile should be multi-stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY . .
2. Volume Mounts
YAML

# Development - mount code for hot reload
volumes:
  - ./backend:/app

# Production - copy code into image, no mount
🤖 Multi-Agent System Design
Agent Responsibilities (Future Implementation)
Python

# Retriever Agent
- Input: User query
- Output: Ranked list of relevant chunks
- Tools: pgvector similarity search

# Analyzer Agent  
- Input: Retrieved chunks + query
- Output: Extracted data points, comparisons
- Tools: LLM with structured output (JSON mode)

# Writer Agent
- Input: Analysis results
- Output: Formatted report with citations
- Tools: LLM with prompt template
Communication Pattern
Python

# Use LangGraph for orchestration
from langgraph.graph import StateGraph

workflow = StateGraph(State)
workflow.add_node("retrieve", retriever_agent)
workflow.add_node("analyze", analyzer_agent)
workflow.add_node("write", writer_agent)
workflow.add_edge("retrieve", "analyze")
workflow.add_edge("analyze", "write")
📊 Vector Embeddings Guidelines
When to Generate Embeddings
Python

# ✅ Generate embeddings for:
- Document chunks (for semantic search)
- User queries (to find similar chunks)

# ❌ Don't generate embeddings for:
- Document metadata (use SQL filters)
- Exact matches (use full-text search)
Embedding Consistency
Python

# ✅ CORRECT - Same model for indexing and querying
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions

# Store in DB
chunk.embedding = await generate_embedding(chunk.content, model=EMBEDDING_MODEL)

# Query
query_embedding = await generate_embedding(user_query, model=EMBEDDING_MODEL)
Never mix embedding models. Always use the same model that created the stored embeddings.

🎨 API Design Principles
RESTful Routes
Python

# ✅ CORRECT - RESTful naming
POST   /api/v1/documents          # Create (upload)
GET    /api/v1/documents          # List all
GET    /api/v1/documents/{id}     # Get one
PUT    /api/v1/documents/{id}     # Update
DELETE /api/v1/documents/{id}     # Delete

# ❌ WRONG - Non-RESTful
POST   /api/v1/upload_document
GET    /api/v1/get_all_documents
Versioning
Always use /api/v1/ prefix. When breaking changes needed, create /api/v2/.

Response Structure
Python

# ✅ CORRECT - Consistent structure
{
  "message": "Success",
  "data": { ... },
  "meta": {
    "total": 10,
    "page": 1
  }
}

# ❌ WRONG - Inconsistent
{
  "result": { ... },  # Sometimes "data", sometimes "result"
  "count": 10         # Sometimes "total", sometimes "count"
}
📝 Documentation Standards
Docstrings (Required for All Functions)
Python

async def upload_document(
    self,
    file: UploadFile,
    title: str | None = None,
) -> Document:
    """
    Upload and process a financial document.
    
    Validates file type and size, creates database record,
    saves file to storage, and queues for background processing.
    
    Args:
        file: Uploaded file (PDF, TXT, or CSV)
        title: Optional human-readable title
        
    Returns:
        Document: Created document record with pending status
        
    Raises:
        HTTPException: If file validation fails
    """
Comments (Use Sparingly)
Python

# ✅ CORRECT - Comments explain WHY, not WHAT
# Reset file pointer to start after reading for size check
await file.seek(0)

# ❌ WRONG - Comment just repeats code
# Seek to position 0
await file.seek(0)
Rule: Code should be self-explanatory. Comments explain non-obvious decisions.

🚨 Common Pitfalls to Avoid
1. Forgetting to Await
Python

# ❌ WRONG
result = db.execute(query)  # Returns coroutine, not result!

# ✅ CORRECT
result = await db.execute(query)
2. Not Handling Optional Values
Python

# ❌ WRONG
page_number = document.total_pages + 1  # Crashes if total_pages is None

# ✅ CORRECT  
page_number = (document.total_pages or 0) + 1
3. SQL Injection (Prevented by SQLAlchemy)
Python

# ✅ CORRECT - SQLAlchemy parameterizes automatically
select(Document).where(Document.id == user_input)

# ❌ WRONG - Never use f-strings in SQL
db.execute(f"SELECT * FROM documents WHERE id = '{user_input}'")
4. Not Using Transactions
Python

# ✅ CORRECT - Transaction in get_db
async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()  # Commits on success
        except:
            await session.rollback()  # Rollback on error
            raise

# ❌ WRONG - Manual commit/rollback everywhere
🎯 When Assisting with Code
1. Always Ask Context First
Before suggesting code, ask:

"What layer is this? (Route/Service/Model)"
"What's the expected input/output?"
"Are there existing similar functions to follow?"
2. Provide Full Context
Don't just show the changed function. Show:

Where the file is located
What imports are needed
What dependencies need adding to requirements.txt
3. Explain Non-Obvious Code
Python

# ✅ GOOD EXPLANATION
await file.seek(0)
# ☝️ After reading the file to check size, the file pointer is at the end.
# We reset it to the start so we can read it again when saving.
4. Follow Existing Patterns
Look at existing code first:

How are other services structured?
What naming conventions are used?
How are errors handled?
📚 Key Technologies Reference
Technology	What It Does	When to Use
FastAPI	Web framework	All HTTP endpoints
SQLAlchemy	ORM	Database queries
Pydantic	Data validation	API schemas, settings
pgvector	Vector search	Similarity queries
asyncpg	Async DB driver	All database connections
aiofiles	Async file I/O	File uploads/downloads
LangChain	LLM orchestration	Agent workflows
OpenAI	Embeddings + LLM	Text → vectors, analysis
🔄 Development Workflow
Bash

# 1. Start containers
docker compose up -d

# 2. View logs
docker compose logs -f backend

# 3. Make code changes (auto-reload happens)

# 4. Test via API docs
open http://localhost:8000/docs

# 5. If new dependencies added
docker compose down
docker compose up -d --build

# 6. Check database
docker exec -it finsight_postgres psql -U finsight_user -d finsight_db
🎓 Learning Resources
FastAPI Docs: https://fastapi.tiangolo.com/
SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
pgvector: https://github.com/pgvector/pgvector
LangChain: https://python.langchain.com/docs/
Pydantic: https://docs.pydantic.dev/
✅ Code Review Checklist
Before suggesting code as complete:

 Type hints on all function signatures
 Async/await for all I/O operations
 Proper error handling with HTTPException
 Docstrings on public functions
 No hardcoded values (use settings)
 Dependencies injected, not created
 Follows existing file structure
 New dependencies added to requirements.txt
 No secrets in code (use .env)
When in doubt, ask the human developer for clarification. Better to ask than to violate architectural principles.

