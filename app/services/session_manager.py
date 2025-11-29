"""
Session Management Service - Visit tracking and conversation lifecycle.
"""
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
from app.models.session import VisitorSession

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages visitor sessions with visit tracking.
    
    Key Features:
    - Tracks all visits (never deletes)
    - Detects fresh conversations (30min threshold)
    - Archives completed sessions
    - Counts total visits per user
    """
    
    def __init__(self, mongo_client: AsyncIOMotorClient):
        settings = get_settings()
        self.db = mongo_client[settings.mongo_db_name]
        self.sessions_collection = self.db["visitor_sessions"]
        self.session_timeout_minutes = 30
        
    async def get_or_create_session(
        self,
        visitor_id: str,
        session_id: str,
        user_id: Optional[str] = None,
        current_message: str = ""
    ) -> Tuple[VisitorSession, bool]:
        """
        Get active session or create new one.
        
        Logic:
        1. Find most recent session
        2. If > 30 minutes old -> Create NEW session (new visit)
        3. If < 30 minutes -> Continue existing session
        4. Track visit numbers
        
        Returns:
            (session, is_new_visit)
        """
        # Find most recent session for this visitor/user
        query = {"visitor_id": visitor_id}
        if user_id:
            query["user_id"] = user_id
        
        recent_session = await self.sessions_collection.find_one(
            query,
            sort=[("last_message_time", -1)]
        )
        
        is_new_visit = False
        
        if recent_session:
            last_message_time = recent_session.get("last_message_time")
            time_diff = (datetime.utcnow() - last_message_time).seconds / 60
            
            # Check if this is a fresh conversation
            if time_diff > self.session_timeout_minutes:
                # NEW VISIT - Archive old session and create new
                logger.info(f"New visit detected ({time_diff:.0f} min gap) - Creating new session")
                
                # Archive old session
                await self.sessions_collection.update_one(
                    {"_id": recent_session["_id"]},
                    {"$set": {"status": "expired"}}
                )
                
                # Get total visit count
                visit_count = await self.sessions_collection.count_documents({
                    "visitor_id": visitor_id,
                    "status": {"$in": ["expired", "completed"]}
                })
                
                # Create new session
                new_session = VisitorSession(
                    visitor_id=visitor_id,
                    user_id=user_id,
                    session_id=session_id,
                    visit_number=visit_count + 1,
                    start_time=datetime.utcnow(),
                    last_message_time=datetime.utcnow(),
                    messages=[],
                    extracted_data={},  # FRESH START
                    status="active"
                )
                
                session_dict = new_session.dict(exclude={"id"})
                await self.sessions_collection.insert_one(session_dict)
                
                logger.info(f"Created new session - Visit #{new_session.visit_number}")
                is_new_visit = True
                return (new_session, is_new_visit)
            else:
                # Continue existing session
                logger.info(f"Continuing session ({time_diff:.0f} min since last message)")
                session = VisitorSession(**recent_session)
                return (session, False)
        else:
            # First ever visit
            logger.info("First visit - Creating initial session")
            new_session = VisitorSession(
                visitor_id=visitor_id,
                user_id=user_id,
                session_id=session_id,
                visit_number=1,
                start_time=datetime.utcnow(),
                last_message_time=datetime.utcnow(),
                messages=[],
                extracted_data={},
                status="active"
            )
            
            session_dict = new_session.dict(exclude={"id"})
            await self.sessions_collection.insert_one(session_dict)
            
            logger.info("Created first visit session")
            return (new_session, True)
    
    async def update_session(self, session: VisitorSession) -> bool:
        """Update existing session in database."""
        try:
            session.last_updated = datetime.utcnow()
            session.last_message_time = datetime.utcnow()
            
            result = await self.sessions_collection.replace_one(
                {"visitor_id": session.visitor_id, "session_id": session.session_id},
                session.dict(exclude={"id"}),
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    async def get_visit_count(self, visitor_id: str, user_id: Optional[str] = None) -> int:
        """
        Get total number of visits for this visitor/user.
        
        Counts all sessions (active, expired, completed).
        """
        query = {"visitor_id": visitor_id}
        if user_id:
            query["user_id"] = user_id
        
        count = await self.sessions_collection.count_documents(query)
        return count
    
    async def mark_session_completed(self, visitor_id: str, session_id: str) -> bool:
        """Mark session as completed (qualified/converted)."""
        try:
            result = await self.sessions_collection.update_one(
                {"visitor_id": visitor_id, "session_id": session_id},
                {"$set": {"status": "completed", "last_updated": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking session completed: {e}")
            return False
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        from datetime import datetime
        import random
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = random.randint(1000, 9999)
        return f"session_{timestamp}_{random_suffix}"
