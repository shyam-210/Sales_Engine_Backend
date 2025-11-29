"""
Conversation Manager - Natural dialogue flow and intent detection.
Transforms robotic Q&A into smooth, conversational sales assistance.
"""
import logging
from typing import Dict, List, Optional, Any
from app.services.groq_service import GroqEngine

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages natural conversation flow with intent detection and context-aware responses.
    
    Products: CRM, ERP, SalesIQ
    """
    
    PRODUCTS = ["CRM", "ERP", "SalesIQ", "Sales Intelligence", "Chatbot"]
    
    CONVERSATION_STAGES = {
        "greeting": 0,
        "discovery": 1,
        "qualification": 2,
        "engagement": 3,
        "closing": 4
    }
    
    def __init__(self):
        self.groq = GroqEngine()
    
    def detect_intent(self, message: str, conversation_history: List[str]) -> Dict[str, Any]:
        """
        Detect user intent using AI.
        
        Returns:
            {
                "intent": "product_inquiry" | "browsing" | "pricing" | "problem_statement" | "off_topic",
                "products_mentioned": ["CRM"],
                "confidence": 0.85,
                "is_on_topic": True
            }
        """
        history_text = "\n".join(conversation_history[-5:]) if conversation_history else "First message"
        
        prompt = f"""Analyze this sales conversation and determine the user's intent.

CONVERSATION HISTORY:
{history_text}

CURRENT MESSAGE: "{message}"

OUR PRODUCTS: CRM, ERP, SalesIQ (AI chatbots)

CLASSIFY THE INTENT AS ONE OF:
- product_inquiry: Asking about our CRM/ERP/SalesIQ products
- browsing: Just looking, not committed yet
- pricing: Focused on cost/pricing
- problem_statement: Expressing pain points or challenges
- off_topic: Asking about products/services we don't offer

ALSO IDENTIFY:
- Which of our products they're interested in (if any)
- Whether this is on-topic for our business

RESPOND IN JSON:
{{
  "intent": "product_inquiry",
  "products_mentioned": ["CRM"],
  "confidence": 0.9,
  "is_on_topic": true,
  "sentiment": "positive"
}}"""

        try:
            response = self.groq.client.chat.completions.create(
                model=self.groq.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Intent detected: {result.get('intent')} (confidence: {result.get('confidence')})")
            return result
            
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            return {
                "intent": "product_inquiry",
                "products_mentioned": [],
                "confidence": 0.5,
                "is_on_topic": True,
                "sentiment": "neutral"
            }
    
    def generate_conversational_response(
        self,
        message: str,
        intent: Dict[str, Any],
        conversation_history: List[str],
        extracted_data: Dict[str, Any],
        missing_fields: List[str],
        stage: str = "discovery"
    ) -> str:
        """
        Generate natural, context-aware response.
        
        This is the CORE of conversational flow - makes bot feel human.
        """
        history_text = "\n".join(conversation_history[-5:]) if conversation_history else ""
        
        # Build context about what we know
        known_info = []
        if extracted_data.get("visitor_name"):
            known_info.append(f"Name: {extracted_data['visitor_name']}")
        if extracted_data.get("team_size"):
            known_info.append(f"Team size: {extracted_data['team_size']}")
        if extracted_data.get("current_solution"):
            known_info.append(f"Current solution: {extracted_data['current_solution']}")
        if extracted_data.get("pain_points"):
            known_info.append(f"Pain points: {', '.join(extracted_data['pain_points'])}")
        
        context = "\n".join(known_info) if known_info else "Nothing yet"
        
        prompt = f"""You are a friendly, professional sales assistant for a company that provides:
- CRM (Customer Relationship Management)
- ERP (Enterprise Resource Planning)
- SalesIQ (AI-powered chatbots and sales intelligence)

CONVERSATION SO FAR:
{history_text}

USER JUST SAID: "{message}"

DETECTED INTENT: {intent.get('intent')}
PRODUCTS THEY'RE INTERESTED IN: {', '.join(intent.get('products_mentioned', [])) or 'Not specified yet'}
CONVERSATION STAGE: {stage}

WHAT WE KNOW ABOUT THEM:
{context}

WHAT WE STILL NEED:
{', '.join(missing_fields) if missing_fields else 'We have enough info!'}

YOUR TASK:
Generate a natural, warm response that:
1. Acknowledges what they just said
2. Shows understanding of their needs
3. If they're on-topic: Engage deeply, ask ONE natural follow-up question
4. If they're off-topic: Politely redirect to our products (CRM/ERP/SalesIQ)
5. If browsing: Pull them in with value proposition
6. Keep it conversational - NOT robotic!

EXAMPLES OF GOOD RESPONSES:
- "Hey! Welcome! What brings you here today?"
- "I totally get that - speed is crucial. How big is your team, by the way?"
- "We don't handle that, but we're experts in CRM and ERP! What's your biggest business challenge?"
- "Just browsing? No problem! Quick heads up - our CRM is 40% cheaper than Salesforce with better features. Curious about anything specific?"

RESPOND WITH JUST THE MESSAGE (no JSON, no formatting):"""

        try:
            response = self.groq.client.chat.completions.create(
                model=self.groq.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,  # Higher for more natural variation
                max_tokens=400  # Increased to handle detailed responses
            )
            
            bot_response = response.choices[0].message.content.strip()
            
            # Validate response is complete and not empty
            if not bot_response or len(bot_response) < 10:
                logger.warning("Generated response too short, using fallback")
                return self._get_smart_fallback(message, intent, missing_fields, extracted_data)
            
            # Check if response seems truncated (ends mid-sentence)
            if bot_response and not bot_response[-1] in ['.', '!', '?', '😊', '👋']:
                logger.warning(f"Response may be truncated: {bot_response}")
                # Try to complete the sentence or use fallback
                if len(bot_response) < 100:
                    return self._get_smart_fallback(message, intent, missing_fields, extracted_data)
            
            logger.info(f"Generated conversational response: {bot_response[:50]}...")
            return bot_response
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return self._get_smart_fallback(message, intent, missing_fields, extracted_data)
    
    def _get_smart_fallback(
        self, 
        message: str, 
        intent: Dict[str, Any], 
        missing_fields: List[str],
        extracted_data: Dict[str, Any]
    ) -> str:
        """Generate smart fallback response based on context."""
        
        # If asking about products
        if "CRM" in message.upper() or "ERP" in message.upper() or "SALESIQ" in message.upper():
            if "CRM" in message.upper():
                return "Absolutely! Our CRM is built for speed and efficiency - way faster than traditional options and more affordable too. What's most important to you in a CRM?"
            elif "ERP" in message.upper():
                return "Great question! Our ERP system streamlines operations and cuts costs significantly. What's your biggest operational challenge right now?"
            else:
                return "Perfect! SalesIQ is our AI-powered chatbot platform. What kind of automation are you looking for?"
        
        # If off-topic
        if not intent.get('is_on_topic'):
            return "We specialize in CRM, ERP, and SalesIQ solutions! What's your biggest business challenge right now?"
        
        # Based on missing fields
        if "visitor_email" in missing_fields:
            return "I'd love to send you more details! What's the best email to reach you?"
        elif "team_size" in missing_fields:
            return "Got it! How big is your team, by the way? Just want to recommend the right fit."
        elif "current_solution" in missing_fields:
            return "Makes sense! What are you currently using, if anything?"
        elif "pain_points" in missing_fields:
            return "I hear you! What's the biggest challenge you're facing right now?"
        
        # Default engaging response
        return "That's great! Tell me more about what you're looking for - I want to make sure we find the perfect solution for you."
    
    def determine_stage(
        self,
        message_count: int,
        extracted_data: Dict[str, Any],
        intent: Dict[str, Any]
    ) -> str:
        """Determine current conversation stage."""
        
        if message_count == 1:
            return "greeting"
        
        # Has clear intent and some data
        if intent.get('intent') in ['product_inquiry', 'problem_statement'] and extracted_data:
            if len(extracted_data) >= 3:
                return "qualification"
            return "discovery"
        
        # Browsing or uncertain
        if intent.get('intent') == 'browsing':
            return "engagement"
        
        # Pricing focused = closing stage
        if intent.get('intent') == 'pricing':
            return "closing"
        
        return "discovery"
    
    def get_redirect_message(self, off_topic_query: str) -> str:
        """Generate polite redirect for off-topic queries."""
        
        redirects = [
            "We don't handle that directly, but we're experts in CRM, ERP, and SalesIQ! What's your biggest business challenge?",
            "That's outside our wheelhouse, but if you need help with sales, operations, or customer engagement, I'm your person! What are you working on?",
            "We focus on CRM, ERP, and SalesIQ solutions. If you're looking to streamline your business, let's chat! What's your main pain point?"
        ]
        
        import random
        return random.choice(redirects)
    
    def get_engagement_message(self, products_mentioned: List[str]) -> str:
        """Generate message to pull browsers into buyers."""
        
        if "CRM" in products_mentioned:
            return "Just browsing? No worries! Quick heads up - our CRM is faster and 40% cheaper than Salesforce. If you ever need help with sales automation, I'm here! What's your current setup?"
        elif "ERP" in products_mentioned:
            return "Taking a look around? Cool! Our ERP system helps teams cut operational costs by 30%. What's your biggest operations challenge?"
        else:
            return "Just exploring? Perfect! We offer CRM, ERP, and SalesIQ bots - all designed to save you time and money. What kind of solution interests you most?"
