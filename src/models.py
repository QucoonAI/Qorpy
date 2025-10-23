"""
Pydantic Models for API Requests/Responses

This module defines the data structures used for validating
request and response bodies in the FastAPI application.
"""

import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Request/Response models
class QuestionRequest(BaseModel):
    """
    Data model for the '/ask-question' endpoint.
    
    This model is used by FastAPI to validate the incoming request body.
    It ensures that the JSON payload has a required 'question' field
    and that its value is a string.
    """
    question: str  # The user's question to be sent to the RAG system.
    
    # Note: Pydantic models automatically handle the data validation.
    # If a request is received without a 'question' field or if it's not
    # a string, FastAPI will automatically return a 422 Unprocessable Entity
    # error. No explicit 'try...except' error handling is needed here.