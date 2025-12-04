"""
Data Extraction Service - Progressive Lead Qualification
Extracts specific fields from messages incrementally using AI.
"""
from typing import Dict, Any, Optional, List
import logging
from groq import Groq
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# AI Prompt for data extraction
EXTRACTION_PROMPT = """You are a data extraction assistant. Extract the following information from the customer's message. Return ONLY valid JSON.

Extract these fields:
- visitor_name: Full name if mentioned (string or null)
- visitor_email: Email address if mentioned (string or null) - IMPORTANT: Extract ANY email, even test emails like test@123.com
- company: Company/organization name (string or null)
- role: Job title or role (string or null)
- team_size: Number of people/employees (integer or null)
- current_solution: Current CRM/software they use (string or null)
- pain_points: List of problems/challenges mentioned (array of strings)
- budget_indication: Budget hints like "cheap", "expensive", "$500/month" (string or null)
- urgency: Time sensitivity like "ASAP", "next month", "exploring" (string or null)

CRITICAL EMAIL EXTRACTION RULES:
- Extract ANY email address format, even if it looks fake (test@123.com, abc@test.com, etc.)
- If user provides ANYTHING with @ symbol, extract it as email
- Don't validate email authenticity, just extract it

Return format:
{
  "visitor_name": null,
  "visitor_email": null,
  "company": null,
  "role": null,
  "team_size": null,
  "current_solution": null,
  "pain_points": [],
  "budget_indication": null,
  "urgency": null
}
"""


class DataExtractorService:
    """Extracts structured data from messages using Groq AI."""
    
    def __init__(self):
        settings = get_settings()
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        
    def extract_from_message(self, message: str) -> Dict[str, Any]:
        """
        Extract structured data from a single message.
        
        Args:
            message: Customer message text
            
        Returns:
            Dictionary with extracted fields
        """
        try:
            logger.info(f"Extracting data from message: {message[:100]}...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            import json
            extracted = json.loads(response.choices[0].message.content)
            
            logger.info(f"Extracted: {extracted}")
            return extracted
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return self._empty_extraction()
    
    def merge_extractions(
        self, 
        existing: Dict[str, Any], 
        new: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge new extraction with existing data.
        CRITICAL: Preserve existing non-null values.
        Only update if new value is meaningful (not None, not empty).
        Pain points are accumulated.
        """
        merged = existing.copy()
        
        for key, value in new.items():
            if key == "pain_points":
                # Accumulate pain points (never lose them)
                existing_points = set(existing.get("pain_points", []))
                new_points = set(value or [])
                merged["pain_points"] = list(existing_points | new_points)
            elif value is not None and value not in ["", [], {}]:
                # Only update if new value is meaningful
                # AND (existing is empty OR new value is different)
                existing_value = existing.get(key)
                if not existing_value or existing_value in [None, "", [], {}]:
                    # Existing is empty, use new value
                    merged[key] = value
                    logger.debug(f"Merged {key}: {value}")
                else:
                    # Existing has value, keep it (don't overwrite!)
                    logger.debug(f"Preserved existing {key}: {existing_value}")
        
        return merged
    
    def calculate_completeness(self, data: Dict[str, Any]) -> float:
        """
        Calculate data completeness score (0.0 to 1.0).
        
        Critical fields weighted higher:
        - team_size: 30%
        - current_solution: 25%
        - pain_points: 20%
        - company: 10%
        - visitor_name: 10%
        - Others: 5%
        """
        weights = {
            "team_size": 0.30,
            "current_solution": 0.25,
            "pain_points": 0.20,
            "company": 0.10,
            "visitor_name": 0.10,
            "visitor_email": 0.15,
            "role": 0.025,
            "budget_indication": 0.025,
        }
        
        score = 0.0
        
        for field, weight in weights.items():
            value = data.get(field)
            if field == "pain_points":
                # Pain points need at least 1 item
                if value and len(value) > 0:
                    score += weight
            elif value is not None:
                score += weight
        
        return min(score, 1.0)
    
    def get_missing_critical_fields(self, data: Dict[str, Any]) -> List[str]:
        """Return list of missing critical fields."""
        critical_fields = ["team_size", "current_solution", "pain_points", "visitor_email"]
        missing = []
        
        for field in critical_fields:
            value = data.get(field)
            if field == "pain_points":
                if not value or len(value) == 0:
                    missing.append(field)
            elif value is None:
                missing.append(field)
        
        return missing
    
    def generate_next_question(
        self, 
        missing_fields: List[str],
        data: Dict[str, Any],
        last_message: str = ""
    ) -> Optional[str]:
        """
        Generate smart, contextual follow-up question using AI.
        
        First checks if user is disinterested/just browsing - if so, returns polite exit.
        Otherwise generates natural questions to gather missing data.
        """
        if not missing_fields:
            return None
        
        # DISINTEREST DETECTION: Check if user explicitly said not interested
        last_lower = last_message.lower()
        disinterest_signals = [
            "not interested", "just browsing", "just looking", "no thanks",
            "not buying", "don't want", "not now", "maybe later",
            "just checking", "just curious", "not ready"
        ]
        
        if any(signal in last_lower for signal in disinterest_signals):
            logger.info("Disinterest detected - returning polite exit message")
            return "No problem at all! Feel free to explore at your own pace. If you have any questions or want to learn more, just let me know. We're here when you're ready!"
        
        # Build context for AI
        known_info = []
        if data.get("visitor_name"):
            known_info.append(f"Name: {data['visitor_name']}")
        if data.get("company"):
            known_info.append(f"Company: {data['company']}")
        if data.get("team_size"):
            known_info.append(f"Team size: {data['team_size']}")
        if data.get("current_solution"):
            known_info.append(f"Current solution: {data['current_solution']}")
        
        known_str = ", ".join(known_info) if known_info else "Nothing yet"
        
        # What we need
        priority = ["team_size", "current_solution", "pain_points", "visitor_email", "company", "visitor_name"]
        next_field = None
        for field in priority:
            if field in missing_fields:
                next_field = field
                break
        
        if not next_field:
            return None
        
        logger.info(f"Missing fields: {missing_fields}")
        logger.info(f"Already extracted: team_size={data.get('team_size')}, current_solution={data.get('current_solution')}, company={data.get('company')}")
        logger.info(f"Next field to ask about: {next_field}")
        
        # Field descriptions for AI
        field_descriptions = {
            "team_size": "the size of their team/organization",
            "current_solution": "what CRM or sales software they currently use",
            "pain_points": "what problems or challenges they're facing",
            "company": "what company they work for",
            "visitor_name": "their name",
            "visitor_email": "their email address",
            "role": "their job title or role",
            "budget_indication": "their budget expectations"
        }
        
        # Generate natural question using AI
        prompt = f"""You are a friendly, helpful sales assistant having a natural conversation.

Last customer message: "{last_message}"

What you know: {known_str}

What you need to find out: {field_descriptions.get(next_field, next_field)}

Generate a natural, conversational response that:
1. Briefly acknowledges their last message (if relevant)
2. Smoothly asks about {field_descriptions.get(next_field, next_field)}
3. Feels like a real conversation, not a form

Keep it SHORT (1-2 sentences max), friendly, and natural.

Examples of GOOD responses:
- "Nice to meet you, Sarah! What company are you with?"
- "Got it! How large is your team?"
- "Thanks for sharing that. What are you currently using for your CRM?"

Examples of BAD responses (too robotic):
- "Please provide your team size."
- "What is your team size?"

Return ONLY the response text, nothing else."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=100
            )
            
            question = response.choices[0].message.content.strip()
            
            # Remove quotes if AI added them
            question = question.strip('"').strip("'")
            
            if not question:
                raise ValueError("AI generated empty question")
            
            logger.info(f"AI-generated question: {question}")
            return question
            
        except Exception as e:
            logger.error(f"AI question generation failed: {e}")
            # Fallback to basic templates
            templates = {
                "team_size": "How large is your team?",
                "current_solution": "What CRM system are you currently using?",
                "pain_points": "What challenges are you trying to solve?",
                "company": "What company are you with?",
                "visitor_name": "What's your name?",
                "visitor_email": "What's your email address?",
            }
            return templates.get(next_field, "How can I help you further?")
    
    def is_ready_to_qualify(self, completeness: float, data: Dict[str, Any], message_count: int = 0) -> bool:
        """
        Determine if we have enough data to qualify the lead.
        
        LENIENT QUALIFICATION (FIXED):
        - Must have email (critical for follow-up)
        - Must have 60%+ completeness
        - That's it! Don't be too greedy for data.
        
        This prevents the bot from asking too many questions.
        """
        # Email is CRITICAL - can't qualify without it
        has_email = data.get("visitor_email") is not None
        if not has_email:
            logger.info("Not ready: Missing email")
            return False
        
        # Check completeness threshold (lowered to 60%)
        if completeness < 0.6:
            logger.info(f"Not ready: Completeness {completeness:.0%} (need 60%+)")
            return False
        
        # We have email + 60% completeness - that's enough!
        logger.info(f"Ready to qualify! Email: {data.get('visitor_email')}, Completeness: {completeness:.0%} (took {message_count} messages)")
        return True
    
    def _empty_extraction(self) -> Dict[str, Any]:
        """Return empty extraction structure."""
        return {
            "visitor_name": None,
            "visitor_email": None,
            "company": None,
            "role": None,
            "team_size": None,
            "current_solution": None,
            "pain_points": [],
            "budget_indication": None,
            "urgency": None
        }
