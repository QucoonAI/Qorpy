"""
FastAPI Backend for Simplified RAG System
=========================================
REST API endpoints for the 4 core RAG functions:
1. POST /process-document - Complete PDF processing
2. POST /add-document - Add to existing collection  
3. POST /replace-database - Replace entire database
4. POST /ask-question - Ask questions with RAG

Perfect for backend integration!
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import tempfile
import os
from simplified_rag import SimplifiedRAG

# Initialize FastAPI app
app = FastAPI(
    title="Simplified RAG API",
    description="4 core functions for RAG document processing and Q&A",
    version="1.0.0"
)

# Initialize RAG system
rag_system = None

@app.on_event("startup")
async def startup_event():
    """Initialize RAG system on startup"""
    global rag_system
    try:
        rag_system = SimplifiedRAG()
        print("✅ RAG system initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize RAG system: {e}")

# Request/Response models
class QuestionRequest(BaseModel):
    question: str

class ProcessResponse(BaseModel):
    success: bool
    message: str
    data: dict

@app.get("/")
async def root():
    """API health check"""
    return {
        "message": "Simplified RAG API is running!",
        "functions": [
            "POST /process-document - Complete PDF processing",
            "POST /add-document - Add to existing collection", 
            "POST /replace-database - Replace entire database",
            "POST /ask-question - Ask questions with RAG",
            "GET /stats - Get database statistics"
        ]
    }

@app.get("/stats")
async def get_stats():
    """Get database statistics"""
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    try:
        stats = rag_system.get_database_stats()
        documents = rag_system.list_all_documents()
        
        return {
            "success": True,
            "stats": stats,
            "document_count": len(documents),
            "documents": documents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-document")
async def process_document(
    file: UploadFile = File(...),
    document_name: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(200)
):
    """
    FUNCTION 1: Complete PDF Processing Pipeline
    Upload PDF → Process → Chunk → Embed → Store in Pinecone
    """
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Process the document
        result = rag_system.function_1_process_complete_document(
            pdf_path=temp_path,
            document_name=document_name or file.filename,
            chunk_size=chunk_size
        )
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if result['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Document processed successfully",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Processing failed: {result['error']}",
                    "data": result
                }
            )
            
    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add-document")
async def add_document(
    file: UploadFile = File(...),
    document_name: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(200)
):
    """
    FUNCTION 2: Add Document to Existing Collection
    Adds new document without removing existing ones
    """
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Add to collection
        result = rag_system.function_2_add_to_existing_collection(
            pdf_path=temp_path,
            document_name=document_name or file.filename,
            chunk_size=chunk_size
        )
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if result['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Document added to collection successfully",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Adding document failed: {result['error']}",
                    "data": result
                }
            )
            
    except Exception as e:
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/replace-database")
async def replace_database(
    file: UploadFile = File(...),
    document_name: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(200),
    confirm: str = Form(...)
):
    """
    FUNCTION 3: Replace Entire Database
    ⚠️ WARNING: Deletes ALL existing documents and uploads this new one
    Requires confirm="YES" to proceed
    """
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    if confirm != "YES":
        raise HTTPException(
            status_code=400, 
            detail="Must confirm with 'YES' to replace entire database"
        )
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Replace entire database
        result = rag_system.function_3_replace_entire_database(
            pdf_path=temp_path,
            document_name=document_name or file.filename,
            chunk_size=chunk_size
        )
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if result['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Database replaced successfully",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Database replacement failed: {result['error']}",
                    "data": result
                }
            )
            
    except Exception as e:
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask-question")
async def ask_question(request: QuestionRequest):
    """
    FUNCTION 4: Ask Questions with RAG Retrieval
    Query the knowledge base and get AI-generated answers with sources
    """
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG system not initialized")
    
    try:
        result = rag_system.function_4_ask_questions(
            question=request.question
        )
        
        if result['success']:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Question answered successfully",
                    "data": result
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Question processing failed: {result['error']}",
                    "data": result
                }
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Development server runner
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)