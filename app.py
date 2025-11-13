"""
FastAPI Backend for Simplified RAG System
=========================================
REST API endpoints for the 3 core RAG functions:
1. POST /update-vector-db - Add to existing collection
3. POST /replace-vector-db-vectors - Replace entire database
4. POST /ask-question - Ask questions with RAG

Perfect for backend integration!

This file contains the main FastAPI application, REST endpoints,
S3 upload logic, and background task management for the RAG system.
"""

# --- Standard Library Imports ---
import os
import uuid
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
from src.models import QuestionRequest, response

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
S3_BUCKET = os.getenv("S3_BUCKET_NAME")  # S3 bucket from env
S3_REGION = os.getenv("AWS_REGION", "us-east-1")  # AWS region from env
s3_client = boto3.client("s3", region_name=S3_REGION)  # Boto3 S3 client

tasks = {} 


def generate_task_id() -> str:
    return str(uuid.uuid4())


@app.on_event("startup")
async def startup_event():
    """
    Initialize the SimplifiedRAG system on application startup.
    The RAG system is loaded into the global 'rag_system' variable.
    """
    global rag_system  # Declare intention to modify the global variable
    try:
        rag_system = SimplifiedRAG()
        logger.info("RAG system initialized successfully!")  # Changed from print
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {e}")  # Changed from print
        rag_system = None  # Ensure it's None if init fails


@app.get("/", response_model=response)
async def root():
    """
    API Health Check Endpoint
    Verifies that the Simplified RAG API is running and lists available endpoints.
    """

    return {
        "responseCode": "00",
        "responseMessage": "Simplified RAG API is running successfully",
        }


@app.post("/upload_file", response_model=response)
async def upload_document(
    doc_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Uploads a PDF document to the configured S3 bucket.

    Validations:
    - File type must be PDF.
    - File size must not exceed MAX_FILE_SIZE_MB.
    - Uploads to S3 and returns the file URL.
    """
    try:
        # Ensure file is a PDF
        if not file.filename.lower().endswith('.pdf'):
            logger.warning(f"Upload failed: File '{file.filename}' is not a PDF.")
            return {
                "responseCode": "01",
                "responseMessage": "Only PDF files are supported"
            }

        # Read file bytes to check size
        file_bytes = await file.read()
        file_size_mb = len(file_bytes) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            logger.warning(f"Upload failed: File size {file_size_mb:.2f} MB exceeds limit of {MAX_FILE_SIZE_MB} MB.")
            return {
                "responseCode": "01",
                "responseMessage": f"File too large ({file_size_mb:.2f} MB). Max allowed size is {MAX_FILE_SIZE_MB} MB."
            }

        # Reset file pointer
        await file.seek(0)

        # Standardize file name
        s3_key = f"{doc_id.lower().replace(' ', '_')}.pdf"

        logger.info(f"Uploading file '{doc_id}' to s3://{S3_BUCKET}/{s3_key}")

        # Upload file to S3
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": file.content_type}
        )

        # Construct file URL
        file_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"File uploaded successfully to {file_url}")

        return {
            "responseCode": "00",
            "responseMessage": "File uploaded successfully",
            "data": {
                "doc_id": doc_id,
                "file_url": file_url
            }
        }

    except NoCredentialsError:
        logger.error("AWS credentials not found. Failed to upload file.")
        return {
            "responseCode": "01",
            "responseMessage": "AWS credentials not available"
        }

    except ClientError as e:
        logger.error(f"S3 ClientError: {e}")
        return {
            "responseCode": "01",
            "responseMessage": f"Failed to upload file: {e}"
        }

    except Exception as e:
        logger.error(f"Unexpected error during file upload: {e}")
        return {
            "responseCode": "01",
            "responseMessage": f"Unexpected error: {str(e)}"
        }


@app.get("/stats", response_model=response)
async def get_stats():
    """
    Retrieve vector database statistics.

    Returns:
    - Database size and vector stats.
    - List of stored documents.
    """
    try:
        if not rag_system:
            logger.error("GET /stats failed: RAG system not initialized.")
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        # Retrieve stats
        stats = rag_system.get_database_stats()
        documents = rag_system.list_all_documents()
        logger.info(f"Fetched stats successfully: {stats}")

        return {
            "responseCode": "00",
            "responseMessage": "Database statistics fetched successfully",
            "data": {
                "stats": stats,
                "document_count": len(documents),
                "documents": documents
            }
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "responseCode": "01",
            "responseMessage": f"Failed to retrieve database stats: {str(e)}"
        }


@app.post("/insert-doc-vector-db", response_model=response)
async def insert_doc_vector_db(
    background_tasks: BackgroundTasks,
    doc_id: str = Form(...),
):
    """
    Update Vector Database with new Document Embeddings

    This endpoint:
    - Adds the vector embeddings of the given document (by doc_id) to the existing vector database.
    - If no vector database exists, it automatically creates one before adding.
    - The operation runs in the background to avoid blocking API response time.
    """
    try:
        # Check if RAG system is initialized
        if not rag_system:
            logger.error("POST /update-vector-db failed: RAG system not initialized.")
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        task_id = generate_task_id()
        tasks[task_id] = {"status": "running", "message": f"Updating vectors for {doc_id}"}

        # Define the background task
        def background_update():
            """Safely update or create the VectorDB with vectors from the document."""
            try:
                logger.info(f"Starting background update for doc_id: {doc_id}")
                _ = rag_system.add_to_existing_collection(filename=doc_id)
                tasks[task_id]["status"] = "done"
                tasks[task_id]["message"] = f"Successfully updated vectors for {doc_id}"
                logger.info(f"Successfully updated vector database for doc_id: {doc_id}")

            except Exception as e:
                logger.error(f"Background update failed for doc_id {doc_id}: {e}")
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["message"] = f"Failed: {str(e)}"

        # Add background task
        background_tasks.add_task(background_update)

        # Return success response immediately
        return {
            "responseCode": "00",
            "responseMessage": f"Background task started to update or create VectorDB with document vectors for '{doc_id}'.",
            "data": {
                "doc_id": doc_id,
                "task_id": task_id
            }
        }

    except Exception as e:
        logger.error(f"Unexpected error in /update-vector-db: {e}")
        return {
            "responseCode": "01",
            "responseMessage": f"VectorDB update failed: {str(e)}"
        }


@app.post("/replace-document-vectors", response_model=response)
async def replace_document_vectors_endpoint(
    background_tasks: BackgroundTasks,
    doc_id: str = Form(...),
    confirm: str = Form(...)
):
    """
    Replace vectors for a specific document in Pinecone.

    Only deletes vectors associated with the given document (metadata field 'filename').
    Requires confirm="YES" to proceed. Runs in background.
    """
    try:
        # Check if RAG system is initialized
        if not rag_system:
            logger.error("POST /replace-document-vectors failed: RAG system not initialized.")
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        # Confirmation check
        if confirm.lower() != "yes":
            logger.warning(f"POST /replace-document-vectors denied for {doc_id}: Confirmation not 'YES'.")
            return {
                "responseCode": "01",
                "responseMessage": "Must confirm with 'YES' to replace document vectors"
            }

        task_id = generate_task_id()
        tasks[task_id] = {"status": "running", "message": f"Replacing vectors for {doc_id}"}
        
        # Background replacement logic
        def background_replace():
            """Wrapper for background task with error handling."""
            try:
                logger.info(f"Starting background task 'replace_document_vectors' for {doc_id}")
                result = rag_system.replace_specific_document_vectors(filename=doc_id)
                tasks[task_id]["status"] = "done"
                tasks[task_id]["message"] = f"Successfully replaced vectors for {doc_id}"
                logger.info(f"Background task completed for {doc_id}: {result}")

            except Exception as e:
                logger.error(f"Background task failed for {doc_id}: {e}")
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["message"] = f"Failed: {str(e)}"

        # Schedule the background task
        background_tasks.add_task(background_replace)

        # Return structured success response
        return {
            "responseCode": "00",
            "responseMessage": "Document vector replacement started successfully",
            "data": {
                "doc_id": doc_id,
                "task_id": task_id
            }
        }

    except Exception as e:
        logger.error(f"Replace document vectors endpoint error: {str(e)}")
        return {
            "responseCode": "01",
            "responseMessage": f"Document vector replacement failed: {str(e)}"
        }
    

@app.post("/reset-vector-db", response_model=response)
async def reset_vector_db(
    confirm: str = Form(...)
):
    """
    Reset Vector Database

    WARNING: This operation deletes all existing vectors from the database 

    Requires confirm="YES" to proceed.
    """
    try:
        # Check if RAG system is initialized
        if not rag_system:
            logger.error("POST /replace-vector-database-vectors failed: RAG system not initialized.")
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        # Confirmation check
        if confirm.lower() != "yes":
            logger.warning(f"POST /replace-vector-database-vectors denied for doc_id={doc_id}: Confirmation not 'YES'.")
            return {
                "responseCode": "01",
                "responseMessage": "Must confirm with 'YES' to replace entire vector database"
            }
        result = rag_system.reset_vector_database()

        # Return structured success response
        return {
            "responseCode": "00",
            "responseMessage": "Resetting Vector database successfully",
            "data": result
        }

    except Exception as e:
        logger.error(f"Replace vector database error: {str(e)}")
        return {
            "responseCode": "01",
            "responseMessage": f"Vector database replacement failed: {str(e)}"
        }


@app.get("/task-status/{task_id}", response_model=response)
async def task_status(task_id: str):
    """Endpoint to return status of background task"""
    task = tasks.get(task_id)
    if not task:
        return {
            "responseCode": "01",
            "responseMessage": "Task ID not found"
        }
    return {
        "responseCode": "00",
        "responseMessage": "Task status retrieved",
        "data": {"task_id": task_id, "status": task["status"], "message": task["message"]}
    }


@app.post("/ask-question", response_model=response)
async def ask_question(request: QuestionRequest):
    """
    Ask Questions with RAG Retrieval
    Query the knowledge base and get AI-generated answers with sources.
    Returns structured responses similar to admin endpoints.
    """
    try:
        # Check if RAG system is initialized
        if not rag_system:
            logger.error("POST /ask-question failed: RAG system not initialized.")
            return {
                "responseCode": "01",
                "responseMessage": "RAG system not initialized"
            }

        # Log the incoming question
        logger.info(f"Processing question: '{request.question[:50]}...'")

        # Call the main RAG function
        result = rag_system.ask_questions(question=request.question)

        # Handle successful response
        if result.get("success"):
            logger.info("Successfully answered question.")
            return {
                "responseCode": "00",
                "responseMessage": "Question answered successfully",
                "data": result
            }

        # Handle known failure from RAG system
        else:
            error_message = result.get("error", "Unknown error")
            logger.warning(f"Question processing failed: {error_message}")
            return {
                "responseCode": "01",
                "responseMessage": f"Question processing failed: {error_message}",
                "data": result
            }

    except Exception as e:
        logger.error(f"Unexpected error in /ask-question endpoint: {str(e)}")
        return {
            "responseCode": "01",
            "responseMessage": f"Unexpected error: {str(e)}"
        }
