"""
Intelligence Router - Main API endpoints for Sales Intelligence Engine.
Handles chat analysis, lead scoring, progressive qualification, and OTP verification.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, Depends, status
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings, Settings
from app.models.lead import (
    ChatAnalysisRequest,
    AnalysisResponse,
    OTPVerificationRequest,
    OTPVerificationResponse,
    LeadDocument,
    LeadScore,
)
from app.models.session import (
    ExtractionRequest,
    ExtractionResponse,
    QualificationRequest,
    VisitorSession,
)
from app.services.groq_service import GroqEngine
from app.services.crm_service import ZohoCRMService
from app.services.extractor_service import DataExtractorService
from app.services.session_manager import SessionManager
from app.services.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["intelligence"])

# Store OTP codes temporarily (in production, use Redis)
otp_store: Dict[str, str] = {}


def get_mongo_client(settings: Settings = Depends(get_settings)) -> AsyncIOMotorClient:
    """Dependency to get MongoDB client."""
    return AsyncIOMotorClient(settings.mongo_url)


@router.post("/extract", response_model=ExtractionResponse)
async def extract_data(
    request: ExtractionRequest,
    x_salesiq_auth: str = Header(...),
    settings: Settings = Depends(get_settings),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client)
):
    """
    Extract data progressively from customer messages.
    
    Progressive lead qualification - extracts specific fields incrementally,
    accumulates data in MongoDB, and asks smart follow-up questions.
    
    Returns next question to ask or indicates readiness to qualify.
    """
    # Validate authentication
    if x_salesiq_auth != settings.zoho_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    logger.info(f"Extracting data for visitor: {request.visitor_id}")
    
    try:
        # Use Session Manager for proper visit tracking
        session_manager = SessionManager(mongo_client)
        session, is_new_visit = await session_manager.get_or_create_session(
            visitor_id=request.visitor_id,
            session_id=request.session_id,
            user_id=request.user_id,
            current_message=request.message
        )
        
        if is_new_visit:
            logger.info(f"New visit detected - Visit #{session.visit_number}")
        
        # Add message to history
        session.messages.append(request.message)
        
        # ==================== CONVERSATIONAL AI LAYER ====================
        # NEW: Detect intent and generate natural response
        conversation_mgr = ConversationManager()
        
        # Detect user intent
        intent = conversation_mgr.detect_intent(
            message=request.message,
            conversation_history=session.messages
        )
        
        # Update session with intent
        session.detected_intent = intent.get('intent')
        if intent.get('products_mentioned'):
            session.products_interested = intent['products_mentioned']
        
        # Extract data from current message (background)
        extractor = DataExtractorService()
        new_extraction = extractor.extract_from_message(request.message)
        
        # Merge with existing data
        session.extracted_data = extractor.merge_extractions(
            session.extracted_data,
            new_extraction
        )
        
        # Calculate completeness
        session.data_completeness = extractor.calculate_completeness(
            session.extracted_data
        )
        
        # Determine conversation stage
        session.conversation_stage = conversation_mgr.determine_stage(
            message_count=len(session.messages),
            extracted_data=session.extracted_data,
            intent=intent
        )
        
        # Determine if ready to qualify
        ready = extractor.is_ready_to_qualify(
            session.data_completeness,
            session.extracted_data,
            message_count=len(session.messages)
        )
        
        # Get missing fields
        missing_fields = extractor.get_missing_critical_fields(session.extracted_data)
        
        # Generate CONVERSATIONAL response (not robotic!)
        if session.is_qualified:
            # POST-QUALIFICATION: Continue conversational engagement
            # User is already qualified, so answer their questions naturally
            next_question = conversation_mgr.generate_conversational_response(
                message=request.message,
                intent=intent,
                conversation_history=session.messages,
                extracted_data=session.extracted_data,
                missing_fields=[],  # No missing fields, just conversing
                stage="engagement"  # Keep them engaged
            )
        elif ready:
            # Ready to qualify - closing message
            if not session.extracted_data.get('visitor_email'):
                next_question = "Perfect! What's the best email to send you the details?"
            else:
                next_question = None  # Trigger qualification
        elif not intent.get('is_on_topic'):
            # Off-topic - redirect
            next_question = conversation_mgr.get_redirect_message(request.message)
        elif intent.get('intent') == 'browsing':
            # Browser - engage
            next_question = conversation_mgr.get_engagement_message(
                products_mentioned=intent.get('products_mentioned', [])
            )
        else:
            # Generate natural conversational response
            next_question = conversation_mgr.generate_conversational_response(
                message=request.message,
                intent=intent,
                conversation_history=session.messages,
                extracted_data=session.extracted_data,
                missing_fields=missing_fields,
                stage=session.conversation_stage
            )
        
        # Save session with Session Manager
        await session_manager.update_session(session)
        
        logger.info(
            f"Conversational extraction - Stage: {session.conversation_stage}, "
            f"Intent: {intent.get('intent')}, Completeness: {session.data_completeness:.2f}, "
            f"Ready: {ready}"
        )
        
        return ExtractionResponse(
            extracted_data=session.extracted_data,
            next_question=next_question,
            ready_to_qualify=ready,
            completeness=session.data_completeness,
            message_count=len(session.messages),
            visit_number=session.visit_number,
            already_qualified=session.is_qualified
        )
        
    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )


@router.post("/qualify", response_model=AnalysisResponse)
async def qualify_lead(
    request: QualificationRequest,
    x_salesiq_auth: str = Header(...),
    settings: Settings = Depends(get_settings),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client)
):
    """
    Qualify and score a lead based on accumulated session data.
    
    Should only be called when data completeness threshold is met.
    """
    # Validate authentication
    if x_salesiq_auth != settings.zoho_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    logger.info(f"Qualifying lead for visitor: {request.visitor_id}")
    
    try:
        db = mongo_client[settings.mongo_db_name]
        sessions_collection = db["visitor_sessions"]
        
        # Get session
        logger.info(f"Looking for session: visitor_id={request.visitor_id}, session_id={request.session_id}")
        session_doc = await sessions_collection.find_one({
            "visitor_id": request.visitor_id,
            "session_id": request.session_id
        })
        
        if not session_doc:
            # Try finding ANY session for this visitor
            any_session = await sessions_collection.find_one({"visitor_id": request.visitor_id})
            if any_session:
                logger.error(f"Session exists but session_id mismatch! Found: {any_session.get('session_id')}, Looking for: {request.session_id}")
            else:
                logger.error(f"No session at all for visitor: {request.visitor_id}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No session found for visitor: {request.visitor_id}, session: {request.session_id}"
            )
        
        session = VisitorSession(**session_doc)
        
        # Build full transcript from messages
        chat_transcript = "\n".join([f"Customer: {msg}" for msg in session.messages])
        
        # Analyze with Groq
        groq_engine = GroqEngine()
        analysis = groq_engine.analyze_chat_intent(chat_transcript)
        
        # Get total visit count for this visitor (engagement signal!)
        session_manager = SessionManager(mongo_client)
        visit_count = await session_manager.get_visit_count(
            visitor_id=request.visitor_id,
            user_id=session.user_id
        )
        logger.info(f"Total visits for {request.visitor_id}: {visit_count}")
        
        # Calculate lead score WITH visit count bonus
        score_data = groq_engine.calculate_lead_score(analysis, visit_count=visit_count)
        lead_score = LeadScore(**score_data)
        
        # Generate battle card if competitor detected
        battle_card = None
        if analysis.competitor_mentioned or session.extracted_data.get("current_solution"):
            competitor = analysis.competitor_mentioned or session.extracted_data.get("current_solution")
            battle_card = groq_engine.generate_battle_card(competitor)
        
        # Generate summary
        summary = _generate_summary(analysis, lead_score)
        action = _determine_action(lead_score, analysis)
        
        # Update session with qualification results
        session.qualified = True
        session.is_qualified = True  # Mark as qualified for post-qualification tracking
        session.lead_score = lead_score.score
        session.last_updated = datetime.utcnow()
        
        await sessions_collection.update_one(
            {"visitor_id": request.visitor_id, "session_id": request.session_id},
            {"$set": {
                "qualified": True, 
                "is_qualified": True,
                "lead_score": lead_score.score, 
                "last_updated": session.last_updated
            }}
        )
        
        # Store in leads collection
        lead_document = LeadDocument(
            visitor_id=request.visitor_id,
            visitor_email=session.extracted_data.get("visitor_email"),
            visitor_name=session.extracted_data.get("visitor_name"),
            visitor_company=session.extracted_data.get("company"),
            chat_transcript=chat_transcript,
            analysis=analysis,
            score=lead_score,
        )
        
        leads_collection = db[settings.mongo_leads_collection]
        await leads_collection.insert_one(lead_document.dict())
        
        logger.info(f"Lead stored in MongoDB - visitor: {request.visitor_id}")
        
        # Sync to CRM and capture response
        crm_lead_id = None
        crm_synced = False
        crm_sync_error = None
        
        try:
            crm_service = ZohoCRMService()
            crm_lead_id = await crm_service.create_lead(lead_document)
            
            if crm_lead_id:
                crm_synced = True
                logger.info(f"CRM sync successful - Lead ID: {crm_lead_id}")
                
                # Update leads collection
                await leads_collection.update_one(
                    {"visitor_id": request.visitor_id},
                    {
                        "$set": {
                            "synced_to_crm": True,
                            "crm_lead_id": crm_lead_id
                        }
                    }
                )
                
                # Send Cliq alert for high-priority leads
                if lead_score.score >= 70:
                    from app.services.cliq_service import send_cliq_alert
                    
                    is_returning = session_doc.get("visit_count", 1) > 1
                    visit_count = session_doc.get("visit_count", 1)
                    
                    await send_cliq_alert(
                        visitor_name=session.extracted_data.get("visitor_name"),
                        visitor_email=session.extracted_data.get("visitor_email"),
                        visitor_company=session.extracted_data.get("company"),
                        intent=analysis.intent,
                        sentiment=analysis.sentiment,
                        urgency="High" if lead_score.score >= 80 else "Medium",
                        budget_signal=analysis.budget_signal,
                        product_interest=session_doc.get("product_interest", "Not specified"),
                        lead_score=lead_score.score,
                        pain_points=analysis.pain_points,
                        recommended_action=analysis.recommended_action,
                        settings=settings,
                        is_returning=is_returning,
                        visit_count=visit_count
                    )
                
            else:
                crm_sync_error = "CRM returned no Lead ID"
                logger.warning(f"CRM sync returned no Lead ID for {request.visitor_id}")
                
        except Exception as crm_error:
            crm_sync_error = str(crm_error)
            logger.error(f"CRM sync failed: {crm_error}")
        
        # Update session with CRM sync status
        await sessions_collection.update_one(
            {"visitor_id": request.visitor_id, "session_id": request.session_id},
            {
                "$set": {
                    "crm_lead_id": crm_lead_id,
                    "crm_synced": crm_synced,
                    "crm_sync_error": crm_sync_error,
                    "crm_synced_at": datetime.utcnow() if crm_synced else None
                }
            }
        )
        
        logger.info(f"Lead qualified - Score: {lead_score.score}, Category: {lead_score.category}")
        
        return AnalysisResponse(
            visitor_id=request.visitor_id,
            score=lead_score.score,
            category=lead_score.category,
            priority=lead_score.priority,
            summary=summary,
            action=action,
            sentiment=analysis.sentiment,
            intent=analysis.intent,
            budget_signal=analysis.budget_signal,
            pain_points=analysis.pain_points,
            competitor=analysis.competitor_mentioned,
            battle_card=battle_card,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Qualification failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Qualification failed: {str(e)}"
        )


@router.get("/leads/top", response_model=List[AnalysisResponse])
async def get_top_leads(
    limit: int = 3,
    x_salesiq_auth: str = Header(...),
    settings: Settings = Depends(get_settings),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client)
):
    """
    Get the top scoring leads (default 3) for the main dashboard.
    """
    if x_salesiq_auth != settings.zoho_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    try:
        db = mongo_client[settings.mongo_db_name]
        leads_collection = db[settings.mongo_leads_collection]
        
        # Sort by Score DESC, then Date DESC
        cursor = leads_collection.find().sort([
            ("score.score", -1),
            ("timestamp", -1)
        ]).limit(limit)
        
        results = []
        async for doc in cursor:
            lead = LeadDocument(**doc)
            summary = _generate_summary(lead.analysis, lead.score)
            results.append(AnalysisResponse(
                visitor_id=lead.visitor_id,
                score=lead.score.score,
                category=lead.score.category,
                priority=lead.score.priority,
                summary=summary,
                action=lead.analysis.recommended_action,
                sentiment=lead.analysis.sentiment,
                intent=lead.analysis.intent,
                budget_signal=lead.analysis.budget_signal,
                pain_points=lead.analysis.pain_points,
                competitor=lead.analysis.competitor_mentioned,
                battle_card=None
            ))
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to fetch top leads: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/{visitor_id}", response_model=AnalysisResponse)
async def get_lead_data(
    visitor_id: str,
    x_salesiq_auth: str = Header(...),
    settings: Settings = Depends(get_settings),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client)
):
    """
    Get the latest qualified lead data for a visitor (for agent widget).
    
    Returns the most recent lead analysis for display in the sales agent dashboard.
    """
    # Validate authentication
    if x_salesiq_auth != settings.zoho_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    logger.info(f"Fetching lead data for visitor: {visitor_id}")
    
    try:
        db = mongo_client[settings.mongo_db_name]
        leads_collection = db[settings.mongo_leads_collection]
        sessions_collection = db["visitor_sessions"]
        
        # Get most recent lead for this visitor
        lead_doc = await leads_collection.find_one(
            {"visitor_id": visitor_id},
            sort=[("created_at", -1)]
        )
        
        if not lead_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No lead data found for visitor: {visitor_id}"
            )
        
        lead = LeadDocument(**lead_doc)
        
        # Fetch CRM sync status from session
        session_doc = await sessions_collection.find_one(
            {"visitor_id": visitor_id},
            sort=[("last_updated", -1)]
        )
        
        crm_lead_id = None
        crm_synced = False
        crm_sync_error = None
        
        if session_doc:
            crm_lead_id = session_doc.get("crm_lead_id")
            crm_synced = session_doc.get("crm_synced", False)
            crm_sync_error = session_doc.get("crm_sync_error")
        
        # Generate summary using helper function
        summary = _generate_summary(lead.analysis, lead.score)
        
        # Return in same format as /analyze endpoint with CRM status
        return AnalysisResponse(
            visitor_id=lead.visitor_id,
            score=lead.score.score,
            category=lead.score.category,
            priority=lead.score.priority,
            summary=summary,
            action=lead.analysis.recommended_action,
            sentiment=lead.analysis.sentiment,
            intent=lead.analysis.intent,
            budget_signal=lead.analysis.budget_signal,
            pain_points=lead.analysis.pain_points,
            competitor=lead.analysis.competitor_mentioned,
            battle_card=None,  # Can add if needed
            crm_lead_id=crm_lead_id,
            crm_synced=crm_synced,
            crm_sync_error=crm_sync_error
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch lead data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch lead data: {str(e)}"
        )


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_chat(
    request: ChatAnalysisRequest,
    x_salesiq_auth: str = Header(...),
    settings: Settings = Depends(get_settings),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client)
):
    """
    Analyze chat transcript and return lead intelligence (legacy endpoint).
    
    This endpoint analyzes the entire transcript at once.
    For progressive qualification, use /extract and /qualify instead.
    """
    # Validate authentication
    if x_salesiq_auth != settings.zoho_secret:
        logger.warning(f"Unauthorized access attempt - visitor: {request.visitor_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    logger.info(f"Analyzing chat for visitor: {request.visitor_id}")
    logger.info(f"Chat transcript: {request.chat_transcript[:100]}...")
    
    try:
        # Initialize AI engine
        groq_engine = GroqEngine()
        
        # Analyze chat with Groq
        analysis = groq_engine.analyze_chat_intent(request.chat_transcript)
        
        # Calculate lead score
        score_data = groq_engine.calculate_lead_score(analysis)
        lead_score = LeadScore(**score_data)
        
        # Generate battle card if competitor detected
        battle_card = None
        if analysis.competitor_mentioned:
            battle_card = groq_engine.generate_battle_card(
                analysis.competitor_mentioned
            )
        
        # Generate human-readable summary
        summary = _generate_summary(analysis, lead_score)
        
        # Determine action
        action = _determine_action(lead_score, analysis)
        
        # Prepare response
        response = AnalysisResponse(
            visitor_id=request.visitor_id,
            score=lead_score.score,
            category=lead_score.category,
            priority=lead_score.priority,
            summary=summary,
            action=action,
            sentiment=analysis.sentiment,
            intent=analysis.intent,
            budget_signal=analysis.budget_signal,
            pain_points=analysis.pain_points,
            competitor=analysis.competitor_mentioned,
            battle_card=battle_card,
        )
        
        # Store in MongoDB
        lead_document = LeadDocument(
            visitor_id=request.visitor_id,
            visitor_email=request.visitor_email,
            visitor_name=request.visitor_name,
            visitor_company=request.visitor_company,
            chat_transcript=request.chat_transcript,
            analysis=analysis,
            score=lead_score,
        )
        
        db = mongo_client[settings.mongo_db_name]
        collection = db[settings.mongo_leads_collection]
        
        await collection.insert_one(lead_document.dict())
        logger.info(f"Lead stored in MongoDB - visitor: {request.visitor_id}")
        
        # Sync to CRM (non-blocking)
        try:
            crm_service = ZohoCRMService()
            crm_lead_id = await crm_service.create_lead(lead_document)
            
            if crm_lead_id:
                await collection.update_one(
                    {"visitor_id": request.visitor_id},
                    {
                        "$set": {
                            "synced_to_crm": True,
                            "crm_lead_id": crm_lead_id
                        }
                    }
                )
        except Exception as crm_error:
            logger.error(f"CRM sync failed: {crm_error}")
        
        logger.info(
            f"Analysis complete - Score: {lead_score.score}, "
            f"Category: {lead_score.category}, Action: {action}"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post("/verify-otp", response_model=OTPVerificationResponse)
async def verify_otp(request: OTPVerificationRequest):
    """
    Verify OTP code for phone number validation.
    
    In production, integrate with actual OTP service (Twilio, etc.)
    """
    stored_otp = otp_store.get(f"{request.visitor_id}:{request.phone_number}")
    
    if not stored_otp:
        return OTPVerificationResponse(
            verified=False,
            message="No OTP found. Please request a new code.",
            visitor_id=request.visitor_id
        )
    
    if stored_otp == request.otp_code:
        # Clear OTP after successful verification
        del otp_store[f"{request.visitor_id}:{request.phone_number}"]
        
        return OTPVerificationResponse(
            verified=True,
            message="Phone number verified successfully",
            visitor_id=request.visitor_id
        )
    else:
        return OTPVerificationResponse(
            verified=False,
            message="Invalid OTP code",
            visitor_id=request.visitor_id
        )


@router.post("/send-otp")
async def send_otp(
    visitor_id: str,
    phone_number: str
):
    """
    Generate and send OTP to phone number.
    
    In production, integrate with Twilio or similar service.
    For demo purposes, returns the OTP in response.
    """
    import random
    
    # Generate 6-digit OTP
    otp_code = str(random.randint(100000, 999999))
    
    # Store OTP (in production, use Redis with TTL)
    otp_store[f"{visitor_id}:{phone_number}"] = otp_code
    
    logger.info(f"OTP generated for {phone_number}: {otp_code}")
    
    # In production, send via SMS
    # await twilio_client.send_sms(phone_number, f"Your OTP: {otp_code}")
    
    return {
        "success": True,
        "message": "OTP sent successfully",
        "otp_code": otp_code  # Remove this in production!
    }


def _generate_summary(analysis, lead_score: LeadScore) -> str:
    """Generate human-readable summary for agents."""
    pain_summary = ", ".join(analysis.pain_points[:3]) if analysis.pain_points else "None"
    
    return (
        f"{lead_score.category} lead ({lead_score.score}/100). "
        f"Intent: {analysis.intent}, Sentiment: {analysis.sentiment}. "
        f"Key pain points: {pain_summary}. "
        f"Recommended: {analysis.recommended_action}."
    )


def _determine_action(lead_score: LeadScore, analysis) -> str:
    """Determine the exact action text for agents."""
    if lead_score.score > 80:
        return "Call Now - High Priority Lead"
    elif lead_score.score > 50:
        if analysis.recommended_action == "Schedule Demo":
            return "Schedule Demo Call"
        else:
            return "Continue Engagement"
    else:
        return "Add to Nurture Campaign"
