"""
Zoho Cliq alert service for high-priority lead notifications.
"""
import httpx
import logging
from typing import Optional, List
from app.core.config import Settings

logger = logging.getLogger(__name__)


async def send_cliq_alert(
    visitor_name: Optional[str],
    visitor_email: Optional[str],
    visitor_company: Optional[str],
    intent: str,
    sentiment: str,
    urgency: str,
    budget_signal: str,
    product_interest: str,
    lead_score: int,
    pain_points: List[str],
    recommended_action: str,
    settings: Settings,
    is_returning: bool = False,
    visit_count: int = 1
) -> bool:
    """
    Send professional lead alert to Zoho Cliq via bot webhook.
    
    Args:
        visitor_name: Lead's name
        visitor_email: Lead's email
        visitor_company: Lead's company
        intent: Buying/Support/Browsing
        sentiment: Positive/Neutral/Frustrated
        urgency: High/Medium/Low
        budget_signal: High/Low/Null
        product_interest: CRM/ERP/SalesIQ
        lead_score: Score 0-100
        pain_points: List of identified pain points
        recommended_action: Next best action
        settings: Application settings
        is_returning: Whether this is a returning customer
        visit_count: Number of visits
        
    Returns:
        bool: True if alert sent successfully, False otherwise
    """
    
    if not settings.cliq_webhook_token or not settings.cliq_bot_name:
        logger.warning("Cliq credentials missing - skipping alert")
        return False
    
    url = f"https://cliq.zoho.in/api/v2/bots/{settings.cliq_bot_name}/message?zapikey={settings.cliq_webhook_token}"
    
    # Build professional message
    returning_badge = f"[RETURNING CUSTOMER - {visit_count} visits]" if is_returning else "[NEW LEAD]"
    category = "HOT" if lead_score >= 80 else "WARM"
    
    # Format pain points
    pain_points_text = "\n".join(f"- {point}" for point in pain_points) if pain_points else "- None identified"
    
    message = f"""
{returning_badge}

HIGH PRIORITY LEAD ALERT

Lead Score: {lead_score}/100
Category: {category}

CONTACT INFORMATION
Name: {visitor_name or "Not provided"}
Email: {visitor_email or "Not provided"}
Company: {visitor_company or "Not provided"}

QUALIFICATION DETAILS
Intent: {intent}
Sentiment: {sentiment}
Urgency: {urgency}
Budget Signal: {budget_signal}
Product Interest: {product_interest}

PAIN POINTS
{pain_points_text}

RECOMMENDED ACTION
{recommended_action}

ACTION REQUIRED: This lead requires immediate follow-up.
"""
    
    payload = {"text": message.strip()}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                logger.info(f"Cliq alert sent successfully for {visitor_email or visitor_name or 'unknown'}")
                return True
            else:
                logger.error(f"Cliq alert failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error sending Cliq alert: {e}")
        return False
