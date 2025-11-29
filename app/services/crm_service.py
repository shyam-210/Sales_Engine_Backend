"""
Zoho CRM Integration Service.
Syncs analyzed leads to Zoho CRM for sales team follow-up.
"""
import logging
from typing import Optional, Dict, Any
import httpx
from datetime import datetime
from app.core.config import get_settings
from app.models.lead import LeadDocument, GroqAnalysisResult
from app.services.zoho_token_manager import ZohoTokenManager

logger = logging.getLogger(__name__)


class ZohoCRMService:
    """Service for syncing leads to Zoho CRM."""
    
    def __init__(self):
        """Initialize CRM service with configuration."""
        settings = get_settings()
        self.api_url = settings.zoho_crm_api_url
        
        # Check if OAuth is configured (preferred method)
        self.use_oauth = bool(
            settings.zoho_crm_client_id and 
            settings.zoho_crm_refresh_token
        )
        
        if self.use_oauth:
            self.token_manager = ZohoTokenManager()
            self.enabled = True
            logger.info("Zoho CRM integration enabled with OAuth token refresh")
        else:
            # Fallback to manual access token (deprecated)
            self.access_token = settings.zoho_crm_access_token
            self.enabled = bool(self.api_url and self.access_token)
            if self.enabled:
                logger.warning("Zoho CRM using manual access token (will expire in 1 hour). Consider switching to OAuth.")
        
        if not self.enabled:
            logger.warning("Zoho CRM integration disabled - missing credentials")
    
    async def create_lead(self, lead_data: LeadDocument) -> Optional[str]:
        """
        Create a lead in Zoho CRM.
        
        Args:
            lead_data: LeadDocument with complete lead information
            
        Returns:
            CRM lead ID if successful, None otherwise
        """
        if not self.enabled:
            logger.info("CRM sync skipped - integration not configured")
            return None
            
        try:
            # Prepare CRM payload
            crm_payload = {
                "data": [
                    {
                        "Last_Name": lead_data.visitor_name or "Unknown",
                        "Email": lead_data.visitor_email,
                        "Company": lead_data.visitor_company or "Not Provided",
                        "Lead_Source": "SalesIQ - Intelligence AI",
                        "Lead_Status": self._map_category_to_status(
                            lead_data.score.category
                        ),
                        "Rating": lead_data.score.category,  # Hot/Warm/Cold
                        "Description": self._format_description(lead_data),
                        "Intelligence_Score": lead_data.score.score,
                        "AI_Intent": lead_data.analysis.intent,
                        "AI_Sentiment": lead_data.analysis.sentiment,
                        "Budget_Signal": lead_data.analysis.budget_signal,
                        "Recommended_Action": lead_data.analysis.recommended_action,
                        # Custom Field for Widget Integration
                        # User must create "Visitor_ID" field in Zoho CRM Leads module
                        "Visitor_ID": lead_data.visitor_id,
                    }
                ]
            }
            
            # Add competitor info if detected
            if lead_data.analysis.competitor_mentioned:
                crm_payload["data"][0]["Competitor"] = (
                    lead_data.analysis.competitor_mentioned
                )
            
            # Send to Zoho CRM API with automatic token refresh
            result = await self._make_crm_request(
                method="POST",
                endpoint="/crm/v2/Leads",
                payload=crm_payload
            )
            
            if result and result.get("data") and len(result["data"]) > 0:
                lead_id = result["data"][0]["details"]["id"]
                logger.info(f"Lead created in CRM: {lead_id}")
                return lead_id
            else:
                logger.error(f"CRM lead creation failed: {result}")
                return None
                    
        except httpx.HTTPError as e:
            logger.error(f"CRM API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error syncing to CRM: {e}")
            return None
    
    async def update_lead_score(
        self, 
        crm_lead_id: str, 
        new_score: int,
        new_category: str
    ) -> bool:
        """
        Update an existing lead's score in CRM.
        
        Args:
            crm_lead_id: Zoho CRM lead ID
            new_score: Updated lead score
            new_category: Updated category (Hot/Warm/Cold)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            update_payload = {
                "data": [
                    {
                        "id": crm_lead_id,
                        "Intelligence_Score": new_score,
                        "Rating": new_category,
                        "Lead_Status": self._map_category_to_status(new_category),
                    }
                ]
            }
            
            result = await self._make_crm_request(
                method="PUT",
                endpoint="/crm/v2/Leads",
                payload=update_payload
            )
            
            if result:
                logger.info(f"Lead {crm_lead_id} score updated to {new_score}")
                return True
            return False
                
        except Exception as e:
            logger.error(f"Failed to update CRM lead: {e}")
            return False
    
    def _map_category_to_status(self, category: str) -> str:
        """Map lead category to CRM status."""
        mapping = {
            "Hot": "Contacted",
            "Warm": "Open",
            "Cold": "Nurture"
        }
        return mapping.get(category, "Open")
    
    async def _make_crm_request(
        self,
        method: str,
        endpoint: str,
        payload: dict,
        retry: bool = True
    ) -> Optional[dict]:
        """
        Make CRM API request with automatic token refresh on 401.
        
        Args:
            method: HTTP method (POST, PUT, etc.)
            endpoint: API endpoint path
            payload: Request payload
            retry: Whether to retry on 401 error
            
        Returns:
            API response data or None on failure
        """
        try:
            # Get access token (OAuth or manual)
            if self.use_oauth:
                access_token = await self.token_manager.get_access_token()
            else:
                access_token = self.access_token
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(
                    method=method,
                    url=f"{self.api_url}{endpoint}",
                    headers={
                        "Authorization": f"Zoho-oauthtoken {access_token}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                # Handle token expiration (401 Unauthorized)
                if response.status_code == 401 and retry and self.use_oauth:
                    logger.warning("Access token expired, refreshing and retrying...")
                    # Force token refresh
                    self.token_manager.force_refresh()
                    # Retry once with new token
                    return await self._make_crm_request(
                        method, endpoint, payload, retry=False
                    )
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"CRM API HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"CRM API request failed: {e}")
            return None
    
    def _format_description(self, lead_data: LeadDocument) -> str:
        """Format lead description with AI insights."""
        pain_points = "\n".join(
            f"- {point}" for point in lead_data.analysis.pain_points
        )
        
        description = f"""
AI-Analyzed Lead from SalesIQ Chat
Generated: {lead_data.timestamp.strftime('%Y-%m-%d %H:%M UTC')}

INTELLIGENCE SUMMARY:
- Lead Score: {lead_data.score.score}/100
- Intent: {lead_data.analysis.intent}
- Sentiment: {lead_data.analysis.sentiment}
- Budget Signal: {lead_data.analysis.budget_signal}
- Recommended Action: {lead_data.analysis.recommended_action}

IDENTIFIED PAIN POINTS:
{pain_points if pain_points else "- None identified"}

CHAT TRANSCRIPT:
{lead_data.chat_transcript[:500]}...
"""
        return description.strip()
