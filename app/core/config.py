"""
Configuration module for Sales Intelligence Backend.
Manages environment variables and application settings.
"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    app_name: str = "Autonomous Sales Intelligence Engine"
    app_version: str = "2.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    
    # Groq AI Configuration
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    groq_model: str = Field(default="llama3-70b-8192", env="GROQ_MODEL")
    groq_temperature: float = 0.1
    groq_max_tokens: int = 2048
    
    # MongoDB Configuration
    mongo_url: str = Field(..., env="MONGO_URL")
    mongo_db_name: str = Field(default="sales_intelligence", env="MONGO_DB_NAME")
    mongo_leads_collection: str = "leads"
    mongo_analytics_collection: str = "analytics"
    
    # Zoho Configuration
    zoho_secret: str = Field(..., env="ZOHO_SECRET")
    zoho_crm_api_url: Optional[str] = Field(default="https://www.zohoapis.com", env="ZOHO_CRM_API_URL")
    zoho_crm_access_token: Optional[str] = Field(default=None, env="ZOHO_CRM_ACCESS_TOKEN")  # Deprecated - use OAuth
    zoho_salesiq_widget_id: str = Field(default="", env="ZOHO_SALESIQ_WIDGET_ID")
    
    # Zoho CRM OAuth Configuration (for automatic token refresh)
    zoho_crm_client_id: str = Field(default="", env="ZOHO_CRM_CLIENT_ID")
    zoho_crm_client_secret: str = Field(default="", env="ZOHO_CRM_CLIENT_SECRET")
    zoho_crm_refresh_token: str = Field(default="", env="ZOHO_CRM_REFRESH_TOKEN")    
    # Zoho Cliq Configuration
    cliq_webhook_token: Optional[str] = Field(default=None, env="CLIQ_WEBHOOK_TOKEN")
    cliq_bot_name: Optional[str] = Field(default=None, env="CLIQ_BOT_NAME")
    
    # Twilio SMS/OTP Configuration
    twilio_account_sid: str = Field(default="", env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", env="TWILIO_AUTH_TOKEN")
    twilio_verify_service_sid: str = Field(default="", env="TWILIO_VERIFY_SERVICE_SID")
    twilio_phone_number: str = Field(default="", env="TWILIO_PHONE_NUMBER")
    use_mock_twilio: bool = Field(default=True, env="USE_MOCK_TWILIO")  # For testing
    
    # JWT Configuration  
    jwt_secret_key: str = Field(default="", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiration_days: int = Field(default=30, env="JWT_EXPIRATION_DAYS")
    
    # Security
    api_rate_limit: int = 100  # requests per minute
    
    # Lead Scoring Weights
    budget_signal_high_score: int = 40
    intent_buying_score: int = 30
    sentiment_frustrated_score: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
