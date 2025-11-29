"""Data models for Sales Intelligence Engine."""
from .lead import (
    ChatAnalysisRequest,
    GroqAnalysisResult,
    LeadScore,
    AnalysisResponse,
    LeadDocument,
    OTPVerificationRequest,
    OTPVerificationResponse,
)

__all__ = [
    "ChatAnalysisRequest",
    "GroqAnalysisResult",
    "LeadScore",
    "AnalysisResponse",
    "LeadDocument",
    "OTPVerificationRequest",
    "OTPVerificationResponse",
]
