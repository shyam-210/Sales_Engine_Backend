"""
Lead scoring and analytics models.
"""
from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class ChatAnalysisRequest(BaseModel):
    """Request model for chat analysis."""
    visitor_id: str = Field(..., description="Unique visitor identifier from SalesIQ")
    chat_transcript: str = Field(..., description="Complete chat conversation history")
    visitor_email: Optional[str] = None
    visitor_name: Optional[str] = None
    visitor_company: Optional[str] = None


class GroqAnalysisResult(BaseModel):
    """Structured output from Groq LLM analysis."""
    sentiment: Literal["Positive", "Neutral", "Frustrated"] = Field(
        ..., description="Customer sentiment analysis"
    )
    intent: Literal["Buying", "Support", "Browsing"] = Field(
        ..., description="Customer purchase intent"
    )
    budget_signal: Literal["High", "Low", "Null"] = Field(
        ..., description="Budget indicator based on keywords"
    )
    pain_points: List[str] = Field(
        default_factory=list, description="Identified customer pain points"
    )
    recommended_action: Literal[
        "Schedule Demo", "Offer Discount", "Escalate", "Nurture"
    ] = Field(..., description="Next best action for the agent")
    competitor_mentioned: Optional[str] = Field(
        None, description="Competitor name if mentioned"
    )


class LeadScore(BaseModel):
    """Calculated lead score and metadata."""
    score: int = Field(..., ge=0, le=100, description="Lead score (0-100)")
    category: Literal["Hot", "Warm", "Cold"] = Field(
        ..., description="Lead temperature category"
    )
    priority: Literal["High", "Medium", "Low"] = Field(
        ..., description="Follow-up priority"
    )
    

class AnalysisResponse(BaseModel):
    """Complete analysis response sent to SalesIQ."""
    visitor_id: str
    score: int = Field(..., ge=0, le=100)
    category: Literal["Hot", "Warm", "Cold"]
    priority: Literal["High", "Medium", "Low"]
    summary: str = Field(..., description="Human-readable summary for agents")
    action: str = Field(..., description="Recommended next action")
    sentiment: str
    intent: str
    budget_signal: str
    pain_points: List[str]
    competitor: Optional[str] = None
    battle_card: Optional[str] = Field(
        None, description="Competitive battle card if competitor detected"
    )
    # CRM Integration fields
    crm_lead_id: Optional[str] = None
    crm_synced: bool = False
    crm_sync_error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LeadDocument(BaseModel):
    """MongoDB document model for lead storage."""
    visitor_id: str
    visitor_email: Optional[str] = None
    visitor_name: Optional[str] = None
    visitor_company: Optional[str] = None
    chat_transcript: str
    analysis: GroqAnalysisResult
    score: LeadScore
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    synced_to_crm: bool = False
    crm_lead_id: Optional[str] = None


class OTPVerificationRequest(BaseModel):
    """OTP verification request."""
    visitor_id: str
    phone_number: str
    otp_code: str


class OTPVerificationResponse(BaseModel):
    """OTP verification response."""
    verified: bool
    message: str
    visitor_id: str
