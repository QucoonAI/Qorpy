"""
FastAPI Backend for Simplified RAG System (Multi-Tenant)
=========================================================
REST API endpoints for the core RAG functions.
Every endpoint requires `entity_id` which maps to a Pinecone namespace,
providing full tenant isolation.

Endpoints:
1. POST /insert-doc-vector-db    - Upload PDF & add to tenant namespace
2. POST /replace-document-vectors - Replace vectors for a specific document
3. POST /reset-vector-db          - Wipe vectors in a specific namespace
4. POST /create-session           - Generate a new session ID
5. POST /ask-question             - Ask questions with RAG
6. POST /ask-question-stream      - Stream answer via SSE
7. GET  /stats                    - Database statistics (per-tenant or global)
8. GET  /entities                 - List all known namespaces
9. POST /add-qa                   - Add single Q&A pair
10. POST /search-qa               - Search Q&A pairs
11. POST /update-qa               - Update a Q&A pair
12. POST /bulk-add-qa             - Bulk upload Q&A from Excel

Direct PDF upload - no S3 dependency.
"""

# --- Standard Library Imports ---
import os
import uuid
import json
import logging
from typing import Optional

# --- Third-Party Imports ---
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse, StreamingResponse
from mangum import Mangum

# --- Local Application Imports ---
from src.simplified_rag import SimplifiedRAG
from src.models import (
    QuestionRequest, CreateSessionRequest,
    AddQARequest, SearchQARequest, UpdateQARequest, response,
)

# --- Logger Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Simplified RAG API (Multi-Tenant)",
    description="Multi-tenant RAG API — each tenant is isolated via Pinecone namespaces",
    version="3.0.0"
)

# Mangum adapter for AWS Lambda
handler = Mangum(app)

# --- Global State ---
rag_system: Optional[SimplifiedRAG] = None
MAX_FILE_SIZE_MB = 10
tasks = {}


def generate_task_id() -> str:
    return str(uuid.uuid4())


@app.on_event("startup")
async def startup_event():
    """Initialize the SimplifiedRAG system on application startup."""
    global rag_system
    try:
        rag_system = SimplifiedRAG()
        logger.info("RAG system initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {e}")
        rag_system = None


@app.get("/", response_model=response)
async def root():
    """API Health Check Endpoint."""
    return {
        "responseCode": "00",
        "responseMessage": "Simplified RAG API is running successfully",
    }


@app.post("/insert-doc-vector-db", response_model=response)
async def insert_doc_vector_db(
    background_tasks: BackgroundTasks,
    entity_id: str = Form(...),
    doc_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a PDF and add its Q&A pairs to a tenant's namespace.

    - `entity_id` — tenant namespace (e.g. "qorpy-business")
    - Accepts a PDF file directly (no S3).
    - Parses Q&A pairs from the PDF.
    - Generates embeddings and upserts to Pinecone in the tenant's namespace.
    - Runs in the background.
    """
    try:
        if not rag_system:
            logger.error("POST /insert-doc-vector-db failed: RAG system not initialized.")
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            return {
                "responseCode": "01",
                "responseMessage": "Only PDF files are supported"
            }

        # Read file bytes and validate size
        file_bytes = await file.read()
        file_size_mb = len(file_bytes) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            return {
                "responseCode": "01",
                "responseMessage": f"File too large ({file_size_mb:.2f} MB). Max allowed is {MAX_FILE_SIZE_MB} MB."
            }

        task_id = generate_task_id()
        tasks[task_id] = {"status": "running", "message": f"Processing {doc_id}"}

        def background_update():
            try:
                logger.info(f"Starting background add for doc_id: {doc_id} in namespace: {entity_id}")
                result = rag_system.add_to_existing_collection(
                    file_bytes=file_bytes,
                    filename=file.filename,
                    namespace=entity_id,
                )
                if result.get('success'):
                    tasks[task_id]["status"] = "done"
                    tasks[task_id]["message"] = f"Successfully added {doc_id}"
                    tasks[task_id]["result"] = result
                else:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["message"] = result.get('error', 'Unknown error')
                logger.info(f"Background add completed for doc_id: {doc_id}")
            except Exception as e:
                logger.error(f"Background add failed for doc_id {doc_id}: {e}")
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["message"] = f"Failed: {str(e)}"

        background_tasks.add_task(background_update)

        return {
            "responseCode": "00",
            "responseMessage": f"Background task started to process '{doc_id}'.",
            "data": {
                "entity_id": entity_id,
                "doc_id": doc_id,
                "task_id": task_id,
                "file_size_mb": round(file_size_mb, 2),
            }
        }

    except Exception as e:
        logger.error(f"Unexpected error in /insert-doc-vector-db: {e}")
        return {
            "responseCode": "01",
            "responseMessage": f"Failed: {str(e)}"
        }


@app.post("/replace-document-vectors", response_model=response)
async def replace_document_vectors_endpoint(
    background_tasks: BackgroundTasks,
    entity_id: str = Form(...),
    doc_id: str = Form(...),
    confirm: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Replace vectors for a specific document within a tenant namespace.
    Upload new PDF, delete old vectors matching doc_id, and re-index.
    Requires confirm="YES".
    """
    try:
        if not rag_system:
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        if confirm.upper() != "YES":
            return {
                "responseCode": "01",
                "responseMessage": "Must confirm with 'YES' to replace document vectors"
            }

        if not file.filename or not file.filename.lower().endswith('.pdf'):
            return {
                "responseCode": "01",
                "responseMessage": "Only PDF files are supported"
            }

        file_bytes = await file.read()
        file_size_mb = len(file_bytes) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            return {
                "responseCode": "01",
                "responseMessage": f"File too large ({file_size_mb:.2f} MB). Max allowed is {MAX_FILE_SIZE_MB} MB."
            }

        task_id = generate_task_id()
        tasks[task_id] = {"status": "running", "message": f"Replacing vectors for {doc_id}"}

        def background_replace():
            try:
                logger.info(f"Starting background replace for {doc_id} in namespace: {entity_id}")
                result = rag_system.replace_specific_document_vectors(
                    file_bytes=file_bytes,
                    filename=file.filename,
                    namespace=entity_id,
                )
                if result.get('success'):
                    tasks[task_id]["status"] = "done"
                    tasks[task_id]["message"] = f"Successfully replaced vectors for {doc_id}"
                    tasks[task_id]["result"] = result
                else:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["message"] = result.get('error', 'Unknown error')
            except Exception as e:
                logger.error(f"Background replace failed for {doc_id}: {e}")
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["message"] = f"Failed: {str(e)}"

        background_tasks.add_task(background_replace)

        return {
            "responseCode": "00",
            "responseMessage": "Document vector replacement started",
            "data": {
                "entity_id": entity_id,
                "doc_id": doc_id,
                "task_id": task_id,
            }
        }

    except Exception as e:
        logger.error(f"Replace document vectors error: {str(e)}")
        return {
            "responseCode": "01",
            "responseMessage": f"Failed: {str(e)}"
        }


@app.post("/reset-vector-db", response_model=response)
async def reset_vector_db(
    entity_id: str = Form(...),
    confirm: str = Form(...),
):
    """
    Reset (wipe) all vectors in a specific tenant namespace.
    Does NOT affect other tenants.
    Requires confirm="YES".
    """
    try:
        if not rag_system:
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        if confirm.upper() != "YES":
            return {
                "responseCode": "01",
                "responseMessage": "Must confirm with 'YES' to reset the vector database"
            }

        result = rag_system.reset_vector_database(namespace=entity_id)

        return {
            "responseCode": "00",
            "responseMessage": f"Namespace '{entity_id}' reset successfully",
            "data": result
        }

    except Exception as e:
        logger.error(f"Reset vector database error: {str(e)}")
        return {
            "responseCode": "01",
            "responseMessage": f"Failed: {str(e)}"
        }


@app.get("/stats", response_model=response)
async def get_stats():
    """
    Retrieve vector database statistics.
    Returns a breakdown of all namespaces (entity_ids) automatically.
    No parameters required.
    """
    try:
        if not rag_system:
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        # Always pull global stats — Pinecone returns per-namespace counts automatically
        raw_stats = rag_system.index.describe_index_stats()
        logger.info(f"Fetched stats successfully: {raw_stats}")

        namespaces = raw_stats.get("namespaces", {})
        entity_ids = {
            ns: {"vector_count": info.get("vector_count", 0)}
            for ns, info in namespaces.items()
        }

        return {
            "responseCode": "00",
            "responseMessage": "Database statistics fetched successfully",
            "data": {
                "total_vectors": raw_stats.get("total_vector_count", 0),
                "index_name": rag_system.index_name,
                "dimension": raw_stats.get("dimension", 512),
                "entity_ids": entity_ids,
            }
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "responseCode": "01",
            "responseMessage": f"Failed: {str(e)}"
        }


@app.get("/entities", response_model=response)
async def list_entities():
    """
    List all known namespaces (entity_ids) from the Pinecone index.
    Useful for recovery — if a client forgets their entity_id.
    """
    try:
        if not rag_system:
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        stats = rag_system.index.describe_index_stats()
        namespaces = list(stats.get("namespaces", {}).keys())
        logger.info(f"Found {len(namespaces)} namespaces: {namespaces}")

        return {
            "responseCode": "00",
            "responseMessage": f"Found {len(namespaces)} entities",
            "data": {
                "entities": namespaces,
                "count": len(namespaces),
            }
        }

    except Exception as e:
        logger.error(f"Error listing entities: {e}")
        return {
            "responseCode": "01",
            "responseMessage": f"Failed: {str(e)}"
        }


@app.get("/task-status/{task_id}", response_model=response)
async def task_status(task_id: str):
    """Check status of a background task."""
    task = tasks.get(task_id)
    if not task:
        return {
            "responseCode": "01",
            "responseMessage": "Task ID not found"
        }
    return {
        "responseCode": "00",
        "responseMessage": "Task status retrieved",
        "data": {
            "task_id": task_id,
            "status": task["status"],
            "message": task["message"],
        }
    }


@app.post("/create-session", response_model=response)
async def create_session(request: CreateSessionRequest):
    """
    Generate a new session ID for conversation history.
    Clients must pass entity_id to scope the session.
    Returns only the session_id (frontend already has entity_id).
    """
    logger.info(f"Creating session for entity_id: {request.entity_id}")
    session_id = str(uuid.uuid4())
    return {
        "responseCode": "00",
        "responseMessage": "Session created successfully",
        "data": {
            "session_id": session_id,
        }
    }


@app.post("/ask-question-stream")
async def ask_question_stream(request: QuestionRequest):
    """
    Stream an answer token by token using Server-Sent Events (SSE).
    The client receives `data: {"text": "..."}\\n\\n` chunks, then `data: [DONE]\\n\\n`.
    """
    if not rag_system:
        async def error_gen():
            yield f"data: {json.dumps({'text': 'RAG system not initialized'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    def generate():
        try:
            logger.info(f"Streaming question: '{request.question[:50]}...' for entity: {request.entity_id}")
            for text_chunk in rag_system.ask_questions_stream(question=request.question):
                if text_chunk:
                    yield f"data: {json.dumps({'text': text_chunk})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'text': f'⚠️ Error: {str(e)}'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/ask-question", response_model=response)
async def ask_question(request: QuestionRequest):
    """
    Ask a question with RAG retrieval, scoped to the tenant's namespace.
    Uses sub-query decomposition internally for better results.
    """
    try:
        if not rag_system:
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        logger.info(f"Processing question: '{request.question[:50]}...' for entity: {request.entity_id}")
        result = rag_system.ask_questions(
            question=request.question,
            session_id=request.session_id,
            namespace=request.entity_id,
        )

        if result.get("success"):
            logger.info("Successfully answered question.")
            # Return only what the frontend needs
            sources = [
                {
                    "filename": s.get("filename", ""),
                    "category": s.get("category", ""),
                    "section": s.get("section", ""),
                    "relevance_score": s.get("relevance_score", 0),
                }
                for s in result.get("sources", [])
            ]
            return {
                "responseCode": "00",
                "responseMessage": "Question answered successfully",
                "data": {
                    "answer": result.get("answer"),
                    "sources": sources,
                }
            }
        else:
            error_message = result.get("error", "Unknown error")
            logger.warning(f"Question processing failed: {error_message}")
            return {
                "responseCode": "01",
                "responseMessage": f"Question processing failed: {error_message}",
            }

    except Exception as e:
        logger.error(f"Unexpected error in /ask-question: {str(e)}")
        return {
            "responseCode": "01",
            "responseMessage": f"Unexpected error: {str(e)}"
        }


# =========================
# ADMIN ENDPOINTS
# =========================

@app.post("/add-qa", response_model=response)
async def add_qa(request: AddQARequest):
    """Add a single Q&A pair to a tenant's namespace."""
    try:
        if not rag_system:
            return {"responseCode": "01", "responseMessage": "RAG system not initialized"}

        result = rag_system.add_single_qa(
            question=request.question,
            answer=request.answer,
            category=request.category or "General",
            section=request.section or "General",
            namespace=request.entity_id,
        )
        if result.get("success"):
            return {
                "responseCode": "00",
                "responseMessage": "Q&A pair added successfully",
                "data": result,
            }
        return {"responseCode": "01", "responseMessage": result.get("error", "Unknown error")}
    except Exception as e:
        logger.error(f"Error in /add-qa: {e}")
        return {"responseCode": "01", "responseMessage": f"Failed: {str(e)}"}


@app.post("/search-qa", response_model=response)
async def search_qa(request: SearchQARequest):
    """Search existing Q&A pairs by semantic similarity within a tenant's namespace."""
    try:
        if not rag_system:
            return {"responseCode": "01", "responseMessage": "RAG system not initialized"}

        matches = rag_system.search_qa(
            query=request.query,
            top_k=request.top_k or 3,
            namespace=request.entity_id,
        )
        return {
            "responseCode": "00",
            "responseMessage": f"Found {len(matches)} results",
            "data": {"matches": matches},
        }
    except Exception as e:
        logger.error(f"Error in /search-qa: {e}")
        return {"responseCode": "01", "responseMessage": f"Failed: {str(e)}"}


@app.post("/update-qa", response_model=response)
async def update_qa(request: UpdateQARequest):
    """Update an existing Q&A pair within a tenant's namespace."""
    try:
        if not rag_system:
            return {"responseCode": "01", "responseMessage": "RAG system not initialized"}

        result = rag_system.update_qa(
            vector_id=request.vector_id,
            new_answer=request.new_answer,
            new_question=request.new_question,
            namespace=request.entity_id,
        )
        if result.get("success"):
            return {
                "responseCode": "00",
                "responseMessage": "Q&A pair updated successfully",
                "data": result,
            }
        return {"responseCode": "01", "responseMessage": result.get("error", "Unknown error")}
    except Exception as e:
        logger.error(f"Error in /update-qa: {e}")
        return {"responseCode": "01", "responseMessage": f"Failed: {str(e)}"}


@app.post("/bulk-add-qa", response_model=response)
async def bulk_add_qa(
    file: UploadFile = File(...),
    entity_id: str = Form(...),
    category: str = Form("General"),
    section: str = Form("General"),
):
    """
    Bulk-add Q&A pairs from an Excel file (.xlsx) to a tenant's namespace.
    The file must have two columns: Question (col A) and Answer (col B).
    """
    try:
        if not rag_system:
            return {"responseCode": "01", "responseMessage": "RAG system not initialized"}

        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            return {"responseCode": "01", "responseMessage": "Only .xlsx files are supported"}

        import openpyxl
        from io import BytesIO

        file_bytes = await file.read()
        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True)
        ws = wb.active

        qa_pairs = []
        for row in ws.iter_rows(min_row=2, values_only=True):  # skip header row
            q = str(row[0]).strip() if row[0] else ""
            a = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            if q and a:
                qa_pairs.append({"question": q, "answer": a})
        wb.close()

        if not qa_pairs:
            return {"responseCode": "01", "responseMessage": "No valid Q&A pairs found in the Excel file"}

        result = rag_system.bulk_add_qa(
            qa_pairs,
            category=category,
            section=section,
            namespace=entity_id,
        )
        if result.get("success"):
            return {
                "responseCode": "00",
                "responseMessage": f"Successfully added {result.get('pairs_added', 0)} Q&A pairs",
                "data": result,
            }
        return {"responseCode": "01", "responseMessage": result.get("error", "Unknown error")}
    except Exception as e:
        logger.error(f"Error in /bulk-add-qa: {e}")
        return {"responseCode": "01", "responseMessage": f"Failed: {str(e)}"}
