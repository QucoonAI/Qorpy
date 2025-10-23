"""
FastAPI Backend for Simplified RAG System
=========================================
REST API endpoints for the 4 core RAG functions:
1. POST /process-document - Complete PDF processing
2. POST /add-document - Add to existing collection
3. POST /replace-database - Replace entire database
4. POST /ask-question - Ask questions with RAG

Perfect for backend integration!

This file contains the main FastAPI application, REST endpoints,
S3 upload logic, and background task management for the RAG system.
"""

# --- Standard Library Imports ---
import os
import logging  # Added for logging
from typing import Optional

# --- Third-Party Imports ---
import boto3
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks
from botocore.exceptions import NoCredentialsError, ClientError
from fastapi.responses import JSONResponse
from mangum import Mangum

# --- Local Application Imports ---
from src.simplified_rag import SimplifiedRAG
from src.models import QuestionRequest

# --- Logger Setup ---
# Configure logging to replace print()
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Simplified RAG API",
    description="4 core functions for RAG document processing and Q&A",
    version="1.0.0"
)

# Mangum adapter for AWS Lambda
handler = Mangum(app)

# --- Global Initializations ---
rag_system: Optional[SimplifiedRAG] = None  # Type hint for the RAG system instance
MAX_FILE_SIZE_MB = 2  # 2 MB limit
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "simplified-rag-app")  # S3 bucket from env
S3_REGION = os.getenv("AWS_REGION", "us-east-1")  # AWS region from env
s3_client = boto3.client("s3", region_name=S3_REGION)  # Boto3 S3 client


@app.on_event("startup")
async def startup_event():
    """
    Initialize the SimplifiedRAG system on application startup.
    The RAG system is loaded into the global 'rag_system' variable.
    """
    global rag_system  # Declare intention to modify the global variable
    try:
        rag_system = SimplifiedRAG()
        logger.info("✅ RAG system initialized successfully!")  # Changed from print
    except Exception as e:
        logger.error(f"❌ Failed to initialize RAG system: {e}")  # Changed from print
        rag_system = None  # Ensure it's None if init fails


@app.get("/")
async def root():
    """API health check endpoint."""
    # Returns a simple JSON response indicating the API is running
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


@app.post("/upload_file")
async def upload_document(
    file_name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Uploads a PDF document to the configured S3 bucket.
    
    - Validates file type (PDF only).
    - Validates file size (max 2MB).
    - Uploads file to S3 with a clean, standardized key.
    """
    # Ensure file is a PDF
    if not file.filename.lower().endswith('.pdf'):
        logger.warning(f"Upload failed: File '{file.filename}' is not a PDF.")
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read file bytes to check size
    file_bytes = await file.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)

    # Validate file size
    if file_size_mb > MAX_FILE_SIZE_MB:
        logger.warning(f"Upload failed: File size {file_size_mb:.2f} MB exceeds limit of {MAX_FILE_SIZE_MB} MB.") # Changed from print(2)
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({file_size_mb:.2f} MB). Max allowed size is {MAX_FILE_SIZE_MB} MB."
        )

    try:
        # Reset file pointer to the beginning after reading
        await file.seek(0)

        # S3 key and upload
        # Create a standardized S3 key (lowercase, spaces to underscores)
        s3_key = f"{file_name.lower().replace(' ', '_')}.pdf"
        
        logger.info(f"Uploading file '{file_name}' to s3://{S3_BUCKET}/{s3_key}")
        
        # Upload the file object to S3
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": file.content_type}
        )

        # Construct the S3 URL
        file_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"Successfully uploaded file to {file_url}")
        return {"message": "Upload successful", "file_url": file_url}

    except NoCredentialsError:
        logger.error("AWS credentials not found. Failed to upload file.")
        raise HTTPException(status_code=401, detail="AWS credentials not available")
    except ClientError as e:
        logger.error(f"S3 ClientError: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during file upload: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@app.get("/stats")
async def get_stats():
    """Get database statistics"""
    # Check if RAG system is initialized
    if not rag_system:
        logger.error("GET /stats failed: RAG system not initialized.")
        raise HTTPException(status_code=500, detail="RAG system not initialized")

    try:
        # Fetch stats and document list from the RAG system
        stats = rag_system.get_database_stats()
        documents = rag_system.list_all_documents()
        
        logger.info(f"Fetched stats: {stats}, Document count: {len(documents)}")

        return {
            "success": True,
            "stats": stats,
            "document_count": len(documents),
            "documents": documents
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update-database")
async def update_database(
    background_tasks: BackgroundTasks,
    document_name: str = Form(...),
):
    """
    FUNCTION 2: Add Document to Existing Collection
    Adds new document without removing existing ones.
    Runs as a background task.
    """
    # Check if RAG system is initialized
    if not rag_system:
        logger.error("POST /update-database failed: RAG system not initialized.")
        raise HTTPException(status_code=500, detail="RAG system not initialized")

    # Define the background task function
    def background_add():
        """Wrapper function for the background task to include error handling."""
        try:
            logger.info(f"Starting background task 'add_to_existing' for: {document_name}")
            rag_system.function_2_add_to_existing_collection(
                document_name=document_name
            )
            logger.info(f"Successfully completed background task 'add_to_existing' for: {document_name}")
        except Exception as e:
            # Added error handling for background task
            logger.error(f"❌ Background task 'add_to_existing' failed for {document_name}: {e}")

    # Add the function to the background task queue
    background_tasks.add_task(background_add)

    # Return a 202 Accepted response immediately
    return JSONResponse(
        status_code=202,
        content={
            "success": True,
            "message": f"Background task started to add '{document_name}' to collection."
        }
    )


@app.post("/replace-database")
async def replace_database(
    background_tasks: BackgroundTasks,
    document_name: str = Form(...),
    confirm: str = Form(...)
):
    """
    FUNCTION 3: Replace Entire Database
    ⚠️ WARNING: Deletes ALL existing documents and uploads this new one
    Requires confirm="YES" to proceed. Runs as a background task.
    """
    # Check if RAG system is initialized
    if not rag_system:
        logger.error("POST /replace-database failed: RAG system not initialized.")
        raise HTTPException(status_code=500, detail="RAG system not initialized")

    # Confirmation check to prevent accidental deletion
    if confirm.lower() != "yes":
        logger.warning(f"POST /replace-database denied for '{document_name}': Confirmation not 'YES'.")
        raise HTTPException(
            status_code=400,
            detail="Must confirm with 'YES' to replace entire database"
        )

    # Define the background task function
    def background_replace():
        """Wrapper function for the background task to include error handling."""
        try:
            logger.info(f"Starting background task 'replace_database' for: {document_name}")
            rag_system.function_3_replace_entire_database(
                document_name=document_name
            )
            logger.info(f"Successfully completed background task 'replace_database' for: {document_name}")
        except Exception as e:
            # Added error handling for background task
            logger.error(f"❌ Background task 'replace_database' failed for {document_name}: {e}")

    # Add the function to the background task queue
    background_tasks.add_task(background_replace)

    # Return a 202 Accepted response immediately
    return JSONResponse(
        status_code=202,
        content={
            "success": True,
            "message": f"Background database replacement started for '{document_name}'."
        }
    )


@app.post("/ask-question")
async def ask_question(request: QuestionRequest):
    """
    FUNCTION 4: Ask Questions with RAG Retrieval
    Query the knowledge base and get AI-generated answers with sources
    """
    # Check if RAG system is initialized
    if not rag_system:
        logger.error("POST /ask-question failed: RAG system not initialized.")
        raise HTTPException(status_code=500, detail="RAG system not initialized")

    try:
        logger.info(f"Processing question: '{request.question[:50]}...'")
        # Call the main RAG function
        result = rag_system.function_4_ask_questions(
            question=request.question
        )
        
        # Handle successful response
        if result['success']:
            logger.info(f"Successfully answered question.")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Question answered successfully",
                    "data": result
                }
            )
        # Handle failure response from RAG system
        else:
            logger.warning(f"Question processing failed: {result.get('error', 'Unknown error')}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Question processing failed: {result.get('error', 'Unknown error')}",
                    "data": result
                }
            )

    except Exception as e:
        logger.error(f"Unexpected error in /ask-question endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Development server runner
if __name__ == "__main__":
    # This block runs only when the script is executed directly
    # Used for local development and testing
    import uvicorn
    logger.info("Starting Uvicorn server for local development...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)