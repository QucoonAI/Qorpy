# Qorpy RAG — Frontend API Integration Guide (v3 — Multi-Tenant)

> This document is intended for the frontend engineering team. It covers how to integrate the FastAPI/AWS Lambda backend into the **End-User Chat Interface** and the **Admin Dashboard**.

> **Breaking change from v2:** Every endpoint now requires an `entity_id` field. This is the identifier for the specific client app (e.g. `"qorpy-business"`, `"acme-corp"`). It acts as a namespace in Pinecone, guaranteeing that each client's data is completely isolated from all other clients.

---

## Table of Contents

1. [Base Information](#base-information)
2. [How entity_id Works](#how-entity_id-works)
3. [Quick Start Workflows](#quick-start-workflows)
4. [Standard Response Format](#standard-response-format)
5. [Chat Interface Endpoints](#chat-interface-endpoints)
   - [Create a Chat Session](#create-a-chat-session)
   - [Ask a Question](#ask-a-question)
6. [Admin & Document Management Endpoints](#admin--document-management-endpoints)
   - [Upload a PDF Document](#upload-a-pdf-document)
   - [Check Background Task Status](#check-background-task-status)
   - [Get System Stats](#get-system-stats)
   - [List All Entities](#list-all-entities)
   - [Replace an Existing Document](#replace-an-existing-document)
   - [Wipe a Tenant Namespace](#wipe-a-tenant-namespace)
7. [Manual Q&A Management Endpoints](#manual-qa-management-endpoints)
   - [Search Existing Q&As](#search-existing-qas)
   - [Add a Single Q&A](#add-a-single-qa)
   - [Update a Q&A](#update-a-qa)
   - [Bulk Add from Excel](#bulk-add-from-excel)

---

## Base Information

| Property | Value |
|---|---|
| **Base URL (Production)** | `https://gij3liro3kouweizzludyyhbe40dsxcw.lambda-url.us-east-1.on.aws` |
| **Base URL (Local Dev)** | `http://localhost:8000` |
| **Swagger UI** | `{Base URL}/docs` (for reference only) |
| **Content Types** | `application/json` or `multipart/form-data` (per endpoint) |
| **API Version** | `3.0.0` |

---

## How `entity_id` Works

`entity_id` is the single most important field in this API. Here is exactly how it works:

- Each client app (e.g. Qorpy Business, Acme Corp) has its own unique `entity_id` string.
- **You must hardcode this string in your frontend app** for the specific client you are building for.
- On every single API call, you send this `entity_id` as a parameter in the JSON body (or Form data).
- The backend uses it as a **Pinecone namespace** — meaning documents uploaded for `acme-corp` are 100% invisible to `qorpy-business` and vice versa.
- The backend does **not** validate or look up `entity_id` in any database. It trusts whatever you send.

**Example mapping:**

| Client App | entity_id to hardcode |
|---|---|
| Qorpy Business | `"qorpy-business"` |
| Acme Corp | `"acme-corp"` |
| Facility Management | `"facility-001"` |

---

## Quick Start Workflows

### Building the Chat Interface

1. **On widget open** — Call `POST /create-session` with `entity_id` to get a `session_id`.
2. **On message send** — Call `POST /ask-question` with `entity_id`, `session_id`, and the user's message.

### Building the Admin Dashboard

| Goal | Endpoint(s) |
|---|---|
| Upload and train on a PDF | `POST /insert-doc-vector-db` → poll `GET /task-status/{task_id}` |
| Manage manual Q&A entries | `POST /add-qa`, `POST /update-qa`, `POST /search-qa`, `POST /bulk-add-qa` |
| View indexed document metrics | `GET /stats?entity_id=...` |
| List all active client namespaces | `GET /entities` |

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
| `responseCode` | `string` | `"00"` = success; `"01"` = error |
| `responseMessage` | `string` | A human-readable description of the result |
| `data` | `object` | The response payload (may be omitted on some responses) |

---

## Chat Interface Endpoints

### Create a Chat Session

**`POST /create-session`**

Initializes a new conversation session scoped to a specific client. Call this once when the chat widget opens.

**Headers**

```
Content-Type: application/json
```

**Request Body**

```json
{
  "entity_id": "qorpy-business"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The unique identifier for this client app |

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

Sends the user's message to the AI and returns an answer sourced only from that client's knowledge base.

**Headers**

```
Content-Type: application/json
```

**Request Body**

```json
{
  "entity_id": "qorpy-business",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "question": "What is the refund policy?"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace — determines which knowledge base to search |
| `question` | `string` | **Yes** | The user's message |
| `session_id` | `string` | No | Session ID for conversation memory. Omit if stateless |

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Question answered successfully",
  "data": {
    "answer": "The refund policy states that you can return items within 30 days...",
    "sources": [
      {
        "filename": "return_policy_2024.pdf",
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

Uploads a PDF, extracts its content, and trains the AI within a specific client namespace. Processing runs as a background task.

**Headers**

```
Content-Type: multipart/form-data
```

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace to upload the document into |
| `doc_id` | `string` | **Yes** | A unique identifier for this document |
| `file` | `file` | **Yes** | The PDF file to upload (max 10 MB) |

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Background task started to process 'doc_123'.",
  "data": {
    "entity_id": "qorpy-business",
    "doc_id": "doc_123",
    "task_id": "task-uuid-here",
    "file_size_mb": 2.5
  }
}
```

Poll `GET /task-status/{task_id}` to track progress.

---

### Check Background Task Status

**`GET /task-status/{task_id}`**

Returns the current status of a background task. Poll every 3 seconds after a document upload.

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

Returns database metrics and indexed document counts. It automatically returns a breakdown of the vector count for every single `entity_id` currently in the database.

**No parameters required.**

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Database statistics fetched successfully",
  "data": {
    "total_vectors": 890,
    "index_name": "qorpyy",
    "dimension": 512,
    "entity_ids": {
      "qorpy-business": {
        "vector_count": 142
      },
      "acme-corp": {
        "vector_count": 748
      }
    }
  }
}
```

---

### List All Entities

**`GET /entities`**

Lists all active `entity_id` namespaces that have data in the Pinecone index. Useful for recovery and admin oversight.

**No request body or parameters required.**

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Found 3 entities",
  "data": {
    "entities": ["qorpy-business", "acme-corp", "facility-001"],
    "count": 3
  }
}
```

---

### Replace an Existing Document

**`POST /replace-document-vectors`**

Deletes the existing vectors for a given document within a client namespace and replaces them with a new PDF upload. Returns a `task_id` — poll `/task-status/{task_id}` to track completion.

**Headers**

```
Content-Type: multipart/form-data
```

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace the document belongs to |
| `doc_id` | `string` | **Yes** | The ID of the document to replace |
| `confirm` | `string` | **Yes** | Must be exactly `"YES"` to confirm the operation |
| `file` | `file` | **Yes** | The new PDF file |

---

### Wipe a Tenant Namespace

**`POST /reset-vector-db`**

> **Warning:** This permanently deletes **all training data for the specified `entity_id` namespace**. It does **not** affect any other client's data.

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace to wipe |
| `confirm` | `string` | **Yes** | Must be exactly `"YES"` to confirm the operation |

---

## Manual Q&A Management Endpoints

These endpoints allow the admin to manage specific question-answer pairs within a client namespace directly, without a PDF upload.

---

### Search Existing Q&As

**`POST /search-qa`**

Searches a client's knowledge base for entries matching a query. Useful for verifying content before adding duplicates.

**Request Body**

```json
{
  "entity_id": "qorpy-business",
  "query": "password reset",
  "top_k": 5
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace to search in |
| `query` | `string` | **Yes** | The search term |
| `top_k` | `integer` | No | Maximum number of results (default: 3) |

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Found 2 results",
  "data": {
    "matches": [
      {
        "id": "vector-uuid",
        "score": 0.941,
        "question": "How do I reset my password?",
        "answer": "Click Forgot Password on the login screen.",
        "category": "Account",
        "section": "Login",
        "document_id": "doc_123"
      }
    ]
  }
}
```

---

### Add a Single Q&A

**`POST /add-qa`**

Adds a single question-answer pair to a client's knowledge base.

**Request Body**

```json
{
  "entity_id": "qorpy-business",
  "question": "How do I reset my password?",
  "answer": "Click 'Forgot password' on the login screen.",
  "category": "Account",
  "section": "Login"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace to add the Q&A into |
| `question` | `string` | **Yes** | The question text |
| `answer` | `string` | **Yes** | The answer text |
| `category` | `string` | No | Category label (default: `"General"`) |
| `section` | `string` | No | Section label (default: `"General"`) |

---

### Update a Q&A

**`POST /update-qa`**

Updates an existing Q&A entry by its vector ID within a client namespace.

**Request Body**

```json
{
  "entity_id": "qorpy-business",
  "vector_id": "uuid-of-the-saved-vector",
  "new_question": "Updated question?",
  "new_answer": "Updated answer text."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace the vector belongs to |
| `vector_id` | `string` | **Yes** | The unique ID of the vector entry to update (obtained from `/search-qa`) |
| `new_answer` | `string` | **Yes** | The replacement answer text |
| `new_question` | `string` | No | The replacement question text (keeps original if omitted) |

---

### Bulk Add from Excel

**`POST /bulk-add-qa`**

Accepts an `.xlsx` file and bulk-imports Q&A pairs into a client namespace. Column A = Questions, Column B = Answers. Row 1 is treated as a header and will be skipped.

**Headers**

```
Content-Type: multipart/form-data
```

**Request Form Data**

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_id` | `string` | **Yes** | The client namespace to import entries into |
| `file` | `file` | **Yes** | The `.xlsx` file to import |
| `category` | `string` | No | Default category for all imported entries |
| `section` | `string` | No | Default section for all imported entries |

**Response**

```json
{
  "responseCode": "00",
  "responseMessage": "Successfully added 42 Q&A pairs",
  "data": {
    "document_id": "doc-uuid",
    "pairs_added": 42
  }
}
```