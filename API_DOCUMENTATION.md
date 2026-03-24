# Qorpy RAG FAQ - Frontend API Integration Guide

This document is for the frontend engineering team. It explains how to integrate the FastAPI/AWS Lambda backend into both the **End-User Chat Interface** and the **Admin Dashboard**.

## 🚀 Quick Start & Integration Workflows

The API is divided into two main parts based on what you are building:

### 1. Building the Chatbot (End-User UI)
You only need two endpoints for the core chat experience:
1. **Initialize Chat:** When the chat widget opens, call `/create-session` to get a `session_id`.
2. **Send Messages:** When the user sends a message, call `/ask-question` with the user's text and the `session_id`. 


### 2. Building the Admin Dashboard (Content Management UI)
For the admin panel where your team manages the AI's knowledge:
*   **Uploading PDFs:** Use `/insert-doc-vector-db`. This returns a `task_id`. Use `/task-status/{task_id}` to poll until the upload finishes.
*   **Managing Manual Q&As:** Use `/add-qa`, `/update-qa`, `/search-qa`, and `/bulk-add-qa` to directly manage specific question-answer pairs without PDFs.
*   **Metrics:** Use `/stats` to show how many documents are currently indexed.

---

## 🌐 Base Information

*   **Base URL:** `https://gij3liro3kouweizzludyyhbe40dsxcw.lambda-url.us-east-1.on.aws` 
    *(Note: You can view the swagger UI by visiting the `/docs` path, but use the base URL for API calls)*
*   **Standard Response Format:** almost all endpoints return this JSON structure:
    ```json
    {
      "responseCode": "00", // "00" = Success, "01" = Error
      "responseMessage": "Human readable message describing the result",
      "data": {} // The actual payload (optional)
    }
    ```

---

## 💬 1. Chat Interface Endpoints

### 1.1 Create a Chat Session
**`POST /create-session`**
Call this once when a user opens the chat to establish conversation memory.

**Response:**
```json
{
  "responseCode": "00",
  "responseMessage": "Session created successfully",
  "data": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

### 1.2 Ask a Question (Standard)
**`POST /ask-question`**
Send a user's message to the AI.

**Headers:** `Content-Type: application/json`
**Request Body:**
```json
{
  "question": "What is the refund policy?",
  "session_id": "123e4567-e89b-12d3-a456-426614174000" // Use the ID from /create-session
}
```
**Response:**
```json
{
  "responseCode": "00",
  "responseMessage": "Question answered successfully",
  "data": {
    "answer": "The refund policy states that you can return items within 30 days...",
    "sources": [
      {
        "filename": "return_policy_2023.pdf",
        "category": "Refunds",
        "section": "Returns",
        "relevance_score": 0.89
      }
    ]
  }
}
```



## ⚙️ 2. Admin & Document Management Endpoints

### 2.1 Upload a PDF Document
**`POST /insert-doc-vector-db`**
Uploads a PDF, extracts data, and trains the AI. Because this can take time, it runs in the background.

**Headers:** `Content-Type: multipart/form-data`
**Request Form Data:**
*   `doc_id` (Text): A unique string/ID for this document.
*   `file` (File): The PDF file (Max 10MB).

**Response:**
```json
{
  "responseCode": "00",
  "responseMessage": "Background task started...",
  "data": {
    "doc_id": "doc_123",
    "task_id": "task-uuid-here",
    "file_size_mb": 2.5
  }
}
```

### 2.2 Check Background Task Status
**`GET /task-status/{task_id}`**
Poll this endpoint (e.g., every 3 seconds) after uploading a PDF to show a loading spinner in the UI until it finishes.

**Path Parameter:** `task_id` (from the upload response)
**Response:**
```json
{
  "responseCode": "00",
  "responseMessage": "Task status retrieved",
  "data": {
    "task_id": "task-uuid-here",
    "status": "running", // Can be: "running", "done", or "failed"
    "message": "Processing doc_123"
  }
}
```

### 2.3 Get System Stats
**`GET /stats`**
Fetch current database metrics and a list of all trained documents.

**Response:**
```json
{
  "responseCode": "00",
  "responseMessage": "Database statistics fetched successfully",
  "data": {
    "stats": { ... },
    "document_count": 5,
    "documents": ["doc_123", "policy_2024"]
  }
}
```

### 2.4 Replace an Existing Document
**`POST /replace-document-vectors`**
Deletes old training data for a specific document and uploads a new PDF.

**Headers:** `Content-Type: multipart/form-data`
**Request Form Data:**
*   `doc_id` (Text): The ID of the document to replace.
*   `confirm` (Text): Must literally be `"YES"`.
*   `file` (File): The new PDF file.

**(Returns a `task_id` just like the upload endpoint).**

### 2.5 Wipe Database (DANGER)
**`POST /reset-vector-db`**
Deletes ALL training data.

**Request Form Data:**
*   `confirm` (Text): Must literally be `"YES"`.

---

## 📝 3. Admin Manual Q&A Management Endpoints
*Use these endpoints to manually manage specific FAQs without needing a PDF.*

### 3.1 Search Existing Q&As
**`POST /search-qa`**
Search what the AI already knows directly in the admin panel.

**Request Body (JSON):**
```json
{
  "query": "password reset",
  "top_k": 5
}
```

### 3.2 Add a Single Q&A
**`POST /add-qa`**

**Request Body (JSON):**
```json
{
  "question": "How do I reset my password?",
  "answer": "Click 'Forgot password' on the login screen.",
  "category": "Account", // Optional
  "section": "Login" // Optional
}
```

### 3.3 Update a Q&A
**`POST /update-qa`**

**Request Body (JSON):**
```json
{
  "vector_id": "uuid-of-the-saved-vector",
  "new_question": "Updated question?", 
  "new_answer": "Updated answer text"
}
```

### 3.4 Bulk-Add from Excel (.xlsx)
**`POST /bulk-add-qa`**
Upload an Excel file (Col A = Questions, Col B = Answers. Row 1 is treated as headers and skipped).

**Headers:** `Content-Type: multipart/form-data`
**Request Form Data:**
*   `file` (File): The `.xlsx` file.
*   `category` (Text, optional): Default category to assign these.
*   `section` (Text, optional): Default section.
