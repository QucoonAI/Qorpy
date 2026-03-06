"""
Pydantic Models for API Requests/Responses

This module defines the data structures used for validating
request and response bodies in the FastAPI application.
"""

from typing import Any, Optional, Union
from pydantic import BaseModel, Field 

# Request/Response models
class QuestionRequest(BaseModel):
    """
    Data model for the '/ask-question' endpoint.
    
    This model is used by FastAPI to validate the incoming request body.
    It ensures that the JSON payload has a required 'question' field
    and that its value is a string.
    """
    question: str  # The user's question to be sent to the RAG system.
    session_id: Optional[str] = None  # Session ID for conversation history (Redis)
    

class BaseResponse(BaseModel):
    """
    Standard response schema for all API endpoints.
    """
    responseCode: str = Field(..., description="Response code: '00' for success, '01' for failure")
    responseMessage: str = Field(..., description="Detailed message about the operation result")
    
class SuccessResponse(BaseResponse):
    data: Optional[Any] = Field(None, description="Optional data payload (depends on endpoint)")

response = Union[BaseResponse, SuccessResponse]