# Qorpy RAG — Frontend API Integration Guide

> This document is intended for the frontend engineering team. It covers how to integrate the FastAPI/AWS Lambda backend into the **End-User Chat Interface** and the **Admin Dashboard**.

---

## Table of Contents

1. [Base Information](#base-information)
2. [Quick Start Workflows](#quick-start-workflows)
3. [Standard Response Format](#standard-response-format)
4. [Chat Interface Endpoints](#chat-interface-endpoints)
   - [Create a Chat Session](#create-a-chat-session)
   - [Ask a Question](#ask-a-question)
5. [Admin & Document Management Endpoints](#admin--document-management-endpoints)
   - [Upload a PDF Document](#upload-a-pdf-document)
   - [Check Background Task Status](#check-background-task-status)
   - [Get System Stats](#get-system-stats)
   - [Replace an Existing Document](#replace-an-existing-document)
   - [Wipe Database](#wipe-database)
6. [Manual Q&A Management Endpoints](#manual-qa-management-endpoints)
   - [Search Existing Q&As](#search-existing-qas)
   - [Add a Single Q&A](#add-a-single-qa)
   - [Update a Q&A](#update-a-qa)
   - [Bulk Add from Excel](#bulk-add-from-excel)

---

## Base Information

| Property | Value |
|---|---|
| **Base URL** | `https://gij3liro3kouweizzludyyhbe40dsxcw.lambda-url.us-east-1.on.aws` |
| **Swagger UI** | `{Base URL}/docs` (for reference only — do not use for API calls) |
| **Content Types** | `application/json` or `multipart/form-data` (per endpoint) |

---

## Quick Start Workflows

### Building the Chat Interface

When implementing the end-user chat widget, only two endpoints are required:

1. **On widget open** — Call `POST /create-session` to obtain a `session_id`.
2. **On message send** — Call `POST /ask-question` with the user's message and the active `session_id`.

### Building the Admin Dashboard

For the content management panel:

| Goal | Endpoints |
|---|---|
| Upload and train on a PDF | `POST /insert-doc-vector-db` → poll `GET /task-status/{task_id}` |
| Manage manual Q&A entries | `POST /add-qa`, `POST /update-qa`, `POST /search-qa`, `POST /bulk-add-qa` |
| View indexed document metrics | `GET /stats` |

---

## Standard Response Format

Nearly all endpoints return a consistent JSON envelope:

```json
{
  "responseCode": "00",
  "responseMessage": "Human readable message describing the result",
  "data": {}
}
```

| Field | Type | Description |
|---|---|---|
| `responseCode` | `string` | `"00"` indicates success; `"01"` indicates an error |
| `responseMessage` | `string` | A human-readable description of the result |
| `data` | `object` | The response payload (may be omitted on some responses) |

---

## Chat Interface Endpoints

### Create a Chat Session

**`POST /create-session`**

Initializes a new conversation session. Call this once when the chat widget is opened to enable conversation memory across messages.

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Session created successfully",
  "data": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

Store the returned `session_id` and attach it to every subsequent `/ask-question` request.

---

### Ask a Question

**`POST /ask-question`**

Sends the user's message to the AI and returns an answer with source references.

**Headers**

```
Content-Type: application/json
```

**Request Body**

```json
{
  "question": "What is the refund policy?",
  "session_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | `string` | Yes | The user's message |
| `session_id` | `string` | Yes | Session ID obtained from `/create-session` |

**Response**

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

---

## Admin & Document Management Endpoints

### Upload a PDF Document

**`POST /insert-doc-vector-db`**

Uploads a PDF file, extracts its content, and trains the AI against it. Processing runs as a background task. Use `/task-status/{task_id}` to track progress.

**Headers**

```
Content-Type: multipart/form-data
```

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `doc_id` | `string` | Yes | A unique identifier for this document |
| `file` | `file` | Yes | The PDF file to upload (max 10 MB) |

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Background task started",
  "data": {
    "doc_id": "doc_123",
    "task_id": "task-uuid-here",
    "file_size_mb": 2.5
  }
}
```

---

### Check Background Task Status

**`GET /task-status/{task_id}`**

Returns the current status of a background task. Poll this endpoint (recommended interval: every 3 seconds) after a document upload to reflect progress in the UI.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| `task_id` | `string` | The task ID returned by the upload endpoint |

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Task status retrieved",
  "data": {
    "task_id": "task-uuid-here",
    "status": "running",
    "message": "Processing doc_123"
  }
}
```

| `status` Value | Meaning |
|---|---|
| `running` | Task is still in progress |
| `done` | Task completed successfully |
| `failed` | Task encountered an error |

---

### Get System Stats

**`GET /stats`**

Returns current database metrics and a list of all indexed documents.

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Database statistics fetched successfully",
  "data": {
    "stats": {},
    "document_count": 5,
    "documents": ["doc_123", "policy_2024"]
  }
}
```

---

### Replace an Existing Document

**`POST /replace-document-vectors`**

Deletes the existing training data for a given document and replaces it with a new PDF upload. Returns a `task_id` identical to the upload endpoint — poll `/task-status/{task_id}` to track completion.

**Headers**

```
Content-Type: multipart/form-data
```

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `doc_id` | `string` | Yes | The ID of the document to replace |
| `confirm` | `string` | Yes | Must be exactly `"YES"` to confirm the operation |
| `file` | `file` | Yes | The new PDF file |

---

### Wipe Database

**`POST /reset-vector-db`**

> **Warning:** This action permanently deletes **all** training data from the vector database. It cannot be undone.

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `confirm` | `string` | Yes | Must be exactly `"YES"` to confirm the operation |

---

## Manual Q&A Management Endpoints

These endpoints allow the admin to manage specific question-answer pairs directly, without requiring a PDF upload.

---

### Search Existing Q&As

**`POST /search-qa`**

Searches the AI's current knowledge base for entries matching a query. Useful for verifying existing content before adding duplicates.

**Request Body**

```json
{
  "query": "password reset",
  "top_k": 5
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | The search term |
| `top_k` | `integer` | No | Maximum number of results to return |

---

### Add a Single Q&A

**`POST /add-qa`**

Adds a single question-answer pair to the knowledge base.

**Request Body**

```json
{
  "question": "How do I reset my password?",
  "answer": "Click 'Forgot password' on the login screen.",
  "category": "Account",
  "section": "Login"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | `string` | Yes | The question text |
| `answer` | `string` | Yes | The answer text |
| `category` | `string` | No | Category label for this entry |
| `section` | `string` | No | Section label for this entry |

---

### Update a Q&A

**`POST /update-qa`**

Updates an existing Q&A entry by its vector ID.

**Request Body**

```json
{
  "vector_id": "uuid-of-the-saved-vector",
  "new_question": "Updated question?",
  "new_answer": "Updated answer text."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `vector_id` | `string` | Yes | The unique ID of the vector entry to update |
| `new_question` | `string` | Yes | The replacement question text |
| `new_answer` | `string` | Yes | The replacement answer text |

---

### Bulk Add from Excel

**`POST /bulk-add-qa`**

Accepts an `.xlsx` file and bulk-imports Q&A pairs. Column A must contain questions and Column B must contain answers. Row 1 is treated as a header row and will be skipped.

**Headers**

```
Content-Type: multipart/form-data
```

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | `file` | Yes | The `.xlsx` file to import |
| `category` | `string` | No | Default category to assign all imported entries |
| `section` | `string` | No | Default section to assign all imported entries |