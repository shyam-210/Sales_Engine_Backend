"""
Zoho OAuth Token Manager - Handles automatic token refresh.
"""
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ZohoTokenManager:
    """Manages Zoho CRM OAuth tokens with automatic refresh."""
    
    def __init__(self):
        settings = get_settings()
        self.client_id = settings.zoho_crm_client_id
        self.client_secret = settings.zoho_crm_client_secret
        self.refresh_token = settings.zoho_crm_refresh_token
        self.api_url = settings.zoho_crm_api_url
        
        # Determine auth server based on API domain
        # https://www.zohoapis.com -> https://accounts.zoho.com
        # https://www.zohoapis.in -> https://accounts.zoho.in
        # https://www.zohoapis.eu -> https://accounts.zoho.eu
        if ".in" in self.api_url:
            self.auth_url = "https://accounts.zoho.in"
        elif ".eu" in self.api_url:
            self.auth_url = "https://accounts.zoho.eu"
        elif ".com.au" in self.api_url:
            self.auth_url = "https://accounts.zoho.com.au"
        else:
            self.auth_url = "https://accounts.zoho.com"
        
        logger.info(f"Zoho OAuth configured - API: {self.api_url}, Auth: {self.auth_url}")
        
        # In-memory token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
    async def get_access_token(self) -> str:
        """
        Get valid access token, refreshing if needed.
        
        Returns:
            Valid access token
            
        Raises:
            Exception if refresh fails
        """
        # Check if current token is still valid
        if self._access_token and self._token_expires_at:
            # Use 5-minute buffer before expiration
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                logger.debug("Using cached access token")
                return self._access_token
        
        # Token expired or doesn't exist - refresh it
        logger.info("Refreshing Zoho CRM access token...")
        await self._refresh_access_token()
        return self._access_token
    
    async def _refresh_access_token(self):
        """
        Refresh access token using refresh token.
        
        Raises:
            Exception if refresh fails
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # Increased timeout
                logger.info(f"Requesting token refresh from {self.auth_url}/oauth/v2/token")
                response = await client.post(
                    f"{self.auth_url}/oauth/v2/token",
                    params={
                        "refresh_token": self.refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token"
                    }
                )
                
                logger.info(f"Token refresh response status: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                
                if "access_token" not in data:
                    logger.error(f"No access_token in response: {data}")
                    raise Exception(f"Invalid token response: {data}")
                
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)  # Default 1 hour
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                logger.info(f"Access token refreshed successfully, expires at {self._token_expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error refreshing access token: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise Exception(f"Failed to refresh Zoho access token: {e}")
        except Exception as e:
            logger.error(f"Unexpected error refreshing access token: {e}")
            raise
    
    def force_refresh(self):
        """Force token refresh on next get_access_token() call."""
        self._token_expires_at = None
