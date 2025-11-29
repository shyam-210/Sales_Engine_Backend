"""
Groq AI Service - The Intelligence Brain.
Analyzes chat conversations using Llama 3 to extract intent, sentiment, and signals.
"""
import json
import logging
from typing import Dict, Any
from groq import Groq
from app.core.config import get_settings
from app.models.lead import GroqAnalysisResult

logger = logging.getLogger(__name__)


class GroqEngine:
    """AI-powered chat analysis engine using Groq's Llama 3."""
    
    SYSTEM_PROMPT = """You are a B2B Sales Analyst. Output STRICT JSON only with these EXACT fields:

{
  "sentiment": "Positive" | "Neutral" | "Frustrated",
  "intent": "Buying" | "Support" | "Browsing",
  "budget_signal": "High" | "Low" | "Null",
  "pain_points": ["specific problem 1", "problem 2"],
  "recommended_action": "Schedule Demo" | "Offer Discount" | "Escalate" | "Nurture",
  "competitor_mentioned": "CompanyName" | null
}

STRICT RULES:
- sentiment: "Positive" for satisfied, "Neutral" for informational, "Frustrated" for unhappy
- intent: "Buying" for ready to purchase, "Browsing" for researching/exploring, "Support" for help/issues
- budget_signal: "High" if mentions enterprise/premium, "Low" if price-sensitive, "Null" if no budget mentioned
- recommended_action: "Schedule Demo" for engaged buyers, "Offer Discount" for price concerns, "Escalate" for frustrated/urgent, "Nurture" for early-stage
- Output ONLY valid JSON, no markdown, no extra text
- Use exact values as shown above"""

    def __init__(self):
        """Initialize Groq client with API key from settings."""
        settings = get_settings()
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        self.temperature = settings.groq_temperature
        self.max_tokens = settings.groq_max_tokens
        
    def analyze_chat_intent(self, chat_history: str) -> GroqAnalysisResult:
        """
        Analyze chat transcript using Groq's Llama 3 model.
        
        Args:
            chat_history: Complete chat conversation transcript
            
        Returns:
            GroqAnalysisResult: Structured analysis with sentiment, intent, signals
        """
        try:
            logger.info(f"Analyzing chat with Groq ({self.model})")
            
            # Call Groq API with JSON mode
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this sales chat:\n\n{chat_history}"}
                ],
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            raw_response = chat_completion.choices[0].message.content
            analysis_dict = json.loads(raw_response)
            
            # Convert to Pydantic model
            analysis = GroqAnalysisResult(**analysis_dict)
            
            logger.info(
                f"Analysis complete - Intent: {analysis.intent}, "
                f"Sentiment: {analysis.sentiment}, "
                f"Budget: {analysis.budget_signal}"
            )
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Groq JSON response: {e}")
            return GroqAnalysisResult(
                sentiment="Neutral",
                intent="Browsing",
                budget_signal="Null",
                pain_points=[],
                recommended_action="Nurture",
                competitor_mentioned=None
            )
        except Exception as e:
            logger.error(f"Groq analysis failed: {str(e)}")
            raise Exception(f"AI analysis failed: {str(e)}")
    
    def calculate_lead_score(self, analysis: GroqAnalysisResult, visit_count: int = 1) -> dict:
        """
        Calculate comprehensive lead score (0-100) including visit frequency.
        
        Scoring Factors:
        - Budget Signal: up to 40 points
        - Intent: up to 30 points
        - Sentiment: up to 20 points
        - Pain Points: up to 10 points
        - Visit Count Bonus: +5 per visit (max +15)
        
        Args:
            analysis: GroqAnalysisResult from Groq
            visit_count: Number of times visitor has come to site
            
        Returns:
            Dict with score, category, priority
        """
        score = 0
        
        # Budget signal (40 points max)
        budget_scores = {"High": 40, "Medium": 25, "Low": 10, "Null": 0}
        score += budget_scores.get(analysis.budget_signal, 0)
        
        # Intent (30 points max)
        intent_scores = {"Buying": 30, "Researching": 20, "Browsing": 10, "Support": 5}
        score += intent_scores.get(analysis.intent, 0)
        
        # Sentiment (20 points max)
        sentiment_scores = {
            "Positive": 20,
            "Neutral": 10,
            "Frustrated": 15,  # Frustrated = opportunity
            "Negative": 5
        }
        score += sentiment_scores.get(analysis.sentiment, 0)
        
        # Pain points (10 points max - 5 per point)
        pain_score = min(len(analysis.pain_points) * 5, 10)
        score += pain_score
        
        # Visit count bonus (engagement signal)
        # More visits = higher buying intent!
        visit_bonus = min((visit_count - 1) * 5, 15)  # +5 per additional visit, max +15
        score += visit_bonus
        
        if visit_count > 1:
            logger.info(f"Visit frequency bonus: +{visit_bonus} points ({visit_count} total visits)")
        
        # Cap at 100
        score = min(score, 100)
        
        # Categorize lead
        if score >= 80:
            category = "Hot"
            priority = "High"
        elif score >= 50:
            category = "Warm"
            priority = "Medium"
        else:
            category = "Cold"
            priority = "Low"
            
        # Frustrated customers always get high priority
        if analysis.sentiment == "Frustrated":
            priority = "High"
            
        return {
            "score": score,
            "category": category,
            "priority": priority
        }
    
    def generate_battle_card(self, competitor: str) -> str:
        """
        Generate competitive battle card for detected competitor.
        
        Args:
            competitor: Name of competitor mentioned
            
        Returns:
            Battle card text with competitive advantages
        """
        battle_cards = {
            "HubSpot": "VS HubSpot: We are 40% cheaper with equivalent features. Superior AI-powered lead scoring. No feature gates on lower tiers.",
            "Salesforce": "VS Salesforce: 60% faster implementation. No complex admin training required. Transparent pricing, no hidden costs.",
            "Intercom": "VS Intercom: Better AI context retention. Seamless CRM integration. 24/7 support included in all plans.",
            "Drift": "VS Drift: More affordable for SMBs. Advanced analytics included. Better customization options.",
            "Zendesk": "VS Zendesk: Purpose-built for sales, not just support. Integrated intelligence engine. Better conversion rates.",
            "Aptean": "VS Aptean: Modern cloud-native architecture. Better mobile experience. More integrations available."
        }
        
        return battle_cards.get(
            competitor,
            f"VS {competitor}: Contact our sales team for detailed competitive comparison."
        )
