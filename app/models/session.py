"""
Extended data models for progressive lead qualification.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class VisitorSession(BaseModel):
    """Tracks visitor session for progressive data gathering."""
    visitor_id: str
    user_id: Optional[str] = None  # Link to authenticated user
    session_id: str
    visit_number: int = 1  # 1st visit, 2nd visit, etc.
    start_time: datetime = Field(default_factory=datetime.utcnow)
    last_message_time: datetime = Field(default_factory=datetime.utcnow)
    messages: List[str] = Field(default_factory=list)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    data_completeness: float = 0.0
    qualified: bool = False
    is_qualified: bool = False  # Track if lead already qualified (for post-qual conversation)
    lead_score: Optional[int] = None
    status: str = "active"  # active, completed, expired
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # Conversational AI fields
    conversation_stage: str = "greeting"  # greeting, discovery, qualification, engagement, closing
    detected_intent: Optional[str] = None  # product_inquiry, browsing, pricing, etc.
    products_interested: List[str] = Field(default_factory=list)  # CRM, ERP, SalesIQ
    
    # CRM Integration fields
    crm_lead_id: Optional[str] = None  # Zoho CRM Lead ID
    crm_synced: bool = False  # Whether lead synced to CRM successfully
    crm_sync_error: Optional[str] = None  # Error message if sync failed
    crm_synced_at: Optional[datetime] = None  # When lead was synced to CRM


class ExtractionRequest(BaseModel):
    """Request for progressive data extraction."""
    visitor_id: str
    session_id: str
    message: str
    user_id: Optional[str] = None  # From auth token if authenticated


class ExtractionResponse(BaseModel):
    """Response from data extraction."""
    extracted_data: Dict[str, Any]
    next_question: Optional[str]
    ready_to_qualify: bool
    completeness: float
    message_count: int
    visit_number: int
    already_qualified: bool = False  # Tells Zobot if lead already qualified


class QualificationRequest(BaseModel):
    """Request to qualify a lead based on accumulated data."""
    visitor_id: str
    session_id: str = "default"
