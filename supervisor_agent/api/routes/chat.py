import asyncio
import json
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from supervisor_agent.api.websocket import notify_chat_update
from supervisor_agent.db import crud, schemas
from supervisor_agent.db.database import get_db
from supervisor_agent.db.enums import ChatThreadStatus, MessageRole, MessageType
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# Chat Thread Endpoints
@router.post("/threads", response_model=schemas.ChatThreadResponse)
async def create_chat_thread(
    thread: schemas.ChatThreadCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a new chat thread"""
    logger.info(f"Creating new chat thread: {thread.title}")
    try:
        # Create thread in database
        db_thread = crud.ChatThreadCRUD.create_thread(db, thread)

        # Create audit log
        audit_data = schemas.AuditLogCreate(
            event_type="CHAT_THREAD_CREATED",
            details={
                "thread_id": str(db_thread.id),
                "title": thread.title,
                "has_initial_message": bool(thread.initial_message),
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        crud.AuditLogCRUD.create_log(db, audit_data)

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update(
                {
                    "type": "thread_created",
                    "thread_id": str(db_thread.id),
                    "title": db_thread.title,
                    "created_at": db_thread.created_at.isoformat(),
                }
            )
        )

        logger.info(f"Created chat thread {db_thread.id}: {thread.title}")
        return db_thread

    except Exception as e:
        logger.error(f"Failed to create chat thread: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads", response_model=schemas.ChatThreadListResponse)
async def get_chat_threads(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ChatThreadStatus] = None,
    db: Session = Depends(get_db),
):
    """Get list of chat threads with statistics"""
    try:
        threads_data = crud.ChatThreadCRUD.get_threads_with_stats(
            db, skip=skip, limit=limit, status=status
        )

        # Convert to response format
        threads = []
        for thread_data in threads_data:
            # Get last message content for preview
            last_message = None
            if thread_data["last_message_at"]:
                messages = crud.ChatMessageCRUD.get_messages(
                    db, thread_data["id"], limit=1
                )
                if messages:
                    last_message = (
                        messages[0].content[:100] + "..."
                        if len(messages[0].content) > 100
                        else messages[0].content
                    )

            thread_response = schemas.ChatThreadResponse(
                id=thread_data["id"],
                title=thread_data["title"],
                description=thread_data["description"],
                status=thread_data["status"],
                created_at=thread_data["created_at"],
                updated_at=thread_data["updated_at"],
                user_id=thread_data["user_id"],
                metadata=thread_data["metadata"],
                unread_count=thread_data["unread_count"],
                last_message=last_message,
                last_message_at=thread_data["last_message_at"],
            )
            threads.append(thread_response)

        # Get total count for pagination
        total_count = len(
            crud.ChatThreadCRUD.get_threads(db, limit=1000)
        )  # Get rough count

        return schemas.ChatThreadListResponse(threads=threads, total_count=total_count)

    except Exception as e:
        logger.error(f"Failed to get chat threads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}", response_model=schemas.ChatThreadResponse)
async def get_chat_thread(thread_id: UUID, db: Session = Depends(get_db)):
    """Get a specific chat thread"""
    try:
        thread = crud.ChatThreadCRUD.get_thread(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        # Get unread count for this thread
        unread_count = crud.ChatNotificationCRUD.get_unread_count(db, thread_id)

        # Get last message
        messages = crud.ChatMessageCRUD.get_messages(db, thread_id, limit=1)
        last_message = None
        last_message_at = None
        if messages:
            last_message = (
                messages[0].content[:100] + "..."
                if len(messages[0].content) > 100
                else messages[0].content
            )
            last_message_at = messages[0].created_at

        # Create response with additional data
        thread_response = schemas.ChatThreadResponse(
            id=thread.id,
            title=thread.title,
            description=thread.description,
            status=thread.status,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            user_id=thread.user_id,
            metadata=thread.metadata,
            unread_count=unread_count,
            last_message=last_message,
            last_message_at=last_message_at,
        )

        return thread_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/threads/{thread_id}", response_model=schemas.ChatThreadResponse)
async def update_chat_thread(
    thread_id: UUID,
    thread_update: schemas.ChatThreadUpdate,
    db: Session = Depends(get_db),
):
    """Update a chat thread"""
    try:
        updated_thread = crud.ChatThreadCRUD.update_thread(db, thread_id, thread_update)
        if not updated_thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update(
                {
                    "type": "thread_updated",
                    "thread_id": str(thread_id),
                    "title": updated_thread.title,
                    "status": updated_thread.status.value,
                }
            )
        )

        logger.info(f"Updated chat thread {thread_id}")
        return updated_thread

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update chat thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/threads/{thread_id}")
async def delete_chat_thread(thread_id: UUID, db: Session = Depends(get_db)):
    """Delete a chat thread"""
    try:
        success = crud.ChatThreadCRUD.delete_thread(db, thread_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update({"type": "thread_deleted", "thread_id": str(thread_id)})
        )

        logger.info(f"Deleted chat thread {thread_id}")
        return {"message": "Chat thread deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete chat thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Chat Message Endpoints
@router.post(
    "/threads/{thread_id}/messages", response_model=schemas.ChatMessageResponse
)
async def send_message(
    thread_id: UUID,
    message: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
):
    """Send a message to a chat thread"""
    try:
        # Verify thread exists
        thread = crud.ChatThreadCRUD.get_thread(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        # Create user message
        db_message = crud.ChatMessageCRUD.create_message(
            db, thread_id, message, MessageRole.USER
        )

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update(
                {
                    "type": "message_sent",
                    "thread_id": str(thread_id),
                    "message_id": str(db_message.id),
                    "content": message.content,
                    "role": "user",
                    "created_at": db_message.created_at.isoformat(),
                }
            )
        )

        # TODO: Process message for task generation if needed
        # This will be implemented in the natural language processing phase

        logger.info(f"Message sent to thread {thread_id}: {len(message.content)} chars")
        return db_message

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send message to thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/{thread_id}/messages/stream")
async def send_message_stream(
    thread_id: UUID,
    message: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
):
    """Send a message with streaming AI response"""
    try:
        # Verify thread exists
        thread = crud.ChatThreadCRUD.get_thread(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        # Create user message if content provided
        if message.content.strip():
            user_message = crud.ChatMessageCRUD.create_message(
                db, thread_id, message, MessageRole.USER
            )

            # Send WebSocket notification for user message
            asyncio.create_task(
                notify_chat_update(
                    {
                        "type": "message_sent",
                        "thread_id": str(thread_id),
                        "message_id": str(user_message.id),
                        "content": message.content,
                        "role": "user",
                        "created_at": user_message.created_at.isoformat(),
                    }
                )
            )

        # Create streaming response for AI
        async def generate_ai_response():
            """Generate streaming AI response"""
            try:
                # Get the AI response content
                ai_content = await generate_ai_response_content(thread_id, message.content, db)
                
                # Stream the response character by character
                accumulated_content = ""
                
                # Send chunks with realistic typing speed
                import asyncio
                for i, char in enumerate(ai_content):
                    accumulated_content += char
                    
                    # Send chunk every few characters or at word boundaries
                    if char.isspace() or i == len(ai_content) - 1 or (i + 1) % 3 == 0:
                        chunk_data = {
                            "type": "chunk",
                            "data": {
                                "id": f"stream_{i}",
                                "delta": char if i == len(accumulated_content) - 1 else accumulated_content[len(accumulated_content) - (i % 3 + 1):],
                                "content": accumulated_content,
                                "finished": i == len(ai_content) - 1,
                            }
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        
                        # Add small delay for realistic typing effect
                        await asyncio.sleep(0.03)  # 30ms delay
                
                # Create the AI message in database
                ai_message_data = schemas.ChatMessageCreate(
                    content=ai_content,
                    message_type=MessageType.TEXT,
                    metadata={"generated": True, "model": "simulated"}
                )
                
                ai_message = crud.ChatMessageCRUD.create_message(
                    db, thread_id, ai_message_data, MessageRole.ASSISTANT
                )

                # Send completion event
                completion_data = {
                    "type": "complete",
                    "data": {
                        "id": str(ai_message.id),
                        "thread_id": str(thread_id),
                        "role": "ASSISTANT",
                        "content": ai_content,
                        "message_type": "TEXT",
                        "metadata": ai_message.message_metadata,
                        "created_at": ai_message.created_at.isoformat(),
                    }
                }
                
                yield f"data: {json.dumps(completion_data)}\n\n"

                # Send WebSocket notification
                asyncio.create_task(
                    notify_chat_update(
                        {
                            "type": "message_sent",
                            "thread_id": str(thread_id),
                            "message_id": str(ai_message.id),
                            "content": ai_content,
                            "role": "assistant",
                            "created_at": ai_message.created_at.isoformat(),
                        }
                    )
                )

            except Exception as e:
                logger.error(f"Error generating AI response: {str(e)}")
                error_data = {
                    "type": "error",
                    "data": {"message": "Failed to generate AI response"}
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate_ai_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start streaming for thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def generate_ai_response_content(thread_id: UUID, user_message: str, db: Session) -> str:
    """
    Generate AI response using the AI Manager with multiple providers
    """
    try:
        # Import AI components
        from supervisor_agent.ai.manager import AIManager, RequestContext
        from supervisor_agent.ai.providers import AIMessage, ModelCapability
        
        # Get recent messages for context
        recent_messages = crud.ChatMessageCRUD.get_messages(db, thread_id, limit=10)
        
        # Convert to AI messages format
        ai_messages = []
        
        # Add system message for context
        ai_messages.append(AIMessage(
            role="system",
            content="""You are an AI supervisor agent designed to help with task management and development workflows. You can assist with:

• Task Creation & Management - Organize and track work
• Code Analysis - Review and improve codebases
• Development Support - Debug issues and implement features
• Workflow Automation - Streamline repetitive processes

Provide helpful, actionable responses that are concise but comprehensive. Focus on practical solutions and next steps."""
        ))
        
        # Add conversation history (reverse to get chronological order)
        for msg in reversed(recent_messages[-5:]):  # Last 5 messages for context
            ai_messages.append(AIMessage(
                role="user" if msg.role == MessageRole.USER else "assistant",
                content=msg.content
            ))
        
        # Add current user message
        ai_messages.append(AIMessage(
            role="user",
            content=user_message
        ))
        
        # Get AI manager instance
        ai_manager = get_ai_manager()
        
        # Create request context
        context = RequestContext(
            thread_id=str(thread_id),
            task_type="chat_response",
            priority="normal",
            required_capabilities=[ModelCapability.TEXT_GENERATION]
        )
        
        # Generate response
        response = await ai_manager.generate_response(
            messages=ai_messages,
            context=context,
            max_tokens=2048,
            temperature=0.7
        )
        
        return response.content
        
    except Exception as e:
        logger.error(f"AI response generation failed: {str(e)}")
        # Fallback to simple response based on keywords
        return generate_fallback_response(user_message)


def generate_fallback_response(user_message: str) -> str:
    """Generate a fallback response when AI providers fail"""
    if "task" in user_message.lower():
        return f"""I'll help you create a task based on your request: "{user_message}".

Here's what I can do for you:

1. **Task Analysis**: I've analyzed your request and identified it as a task creation scenario.

2. **Suggested Actions**:
   - Create a new task in the system
   - Set appropriate priority level
   - Add relevant metadata and context
   - Schedule execution if needed

3. **Next Steps**: Would you like me to proceed with creating this task, or would you like to modify any of the details first?

Let me know how you'd like to proceed, and I'll take care of the task creation for you."""

    elif "help" in user_message.lower():
        return f"""I'm here to help! Based on your message: "{user_message}", here are the ways I can assist you:

🔧 **Development Tasks**:
- Code analysis and review
- Bug fixing and debugging
- Feature implementation
- Refactoring assistance

📋 **Task Management**:
- Create and organize tasks
- Set priorities and deadlines
- Track progress and completion
- Generate reports

🤖 **AI Assistance**:
- Natural language processing
- Intelligent suggestions
- Automated workflows
- Pattern recognition

What specific area would you like help with? I'm ready to dive deep into any technical challenge you're facing."""

    elif "analyze" in user_message.lower():
        return f"""I'll analyze the request: "{user_message}".

📊 **Analysis Results**:

**Intent Detection**: Request for analysis/review
**Complexity Level**: Medium
**Category**: Code/System Analysis
**Estimated Time**: 10-30 minutes

**Recommended Approach**:
1. Gather relevant data and context
2. Apply analytical frameworks
3. Identify patterns and insights
4. Generate actionable recommendations

**Tools Available**:
- Static code analysis
- Performance profiling
- Security scanning
- Quality metrics

Would you like me to proceed with a specific type of analysis, or do you need more information about the available analysis options?"""

    else:
        return f"""I'm experiencing some technical difficulties right now, but I'm here to help with your request: "{user_message}"

I can assist you with:
• Task creation and management
• Code analysis and review
• Development support
• Workflow automation

Please try again in a moment, or let me know if you'd like me to help with something specific in the meantime."""


# Global AI manager instance
_ai_manager = None

def get_ai_manager() -> AIManager:
    """Get or create AI manager instance"""
    global _ai_manager
    if _ai_manager is None:
        from supervisor_agent.ai.manager import AIManagerConfig, ProviderConfig
        import os
        
        # Configuration - in production, load from environment/config file
        from supervisor_agent.ai.context_manager import DEFAULT_CONTEXT_STRATEGY
        
        config = AIManagerConfig(
            providers=[
                ProviderConfig(
                    name="anthropic",
                    provider_class="anthropic",
                    api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                    enabled=bool(os.getenv("ANTHROPIC_API_KEY")),
                    priority=1
                ),
                ProviderConfig(
                    name="openai",
                    provider_class="openai",
                    api_key=os.getenv("OPENAI_API_KEY", ""),
                    enabled=bool(os.getenv("OPENAI_API_KEY")),
                    priority=2
                ),
                ProviderConfig(
                    name="local",
                    provider_class="local",
                    api_key="",
                    base_url=os.getenv("LOCAL_AI_URL", "http://localhost:11434"),
                    enabled=bool(os.getenv("ENABLE_LOCAL_AI", "false").lower() == "true"),
                    priority=3
                ),
            ],
            cost_optimization=True,
            fallback_enabled=True,
            enable_smart_context=True,
            context_strategy=DEFAULT_CONTEXT_STRATEGY
        )
        
        _ai_manager = AIManager(config)
    
    return _ai_manager


@router.get(
    "/threads/{thread_id}/messages",
    response_model=schemas.ChatMessagesListResponse,
)
async def get_messages(
    thread_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    before: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    """Get messages from a chat thread"""
    try:
        # Verify thread exists
        thread = crud.ChatThreadCRUD.get_thread(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        # Get messages
        messages = crud.ChatMessageCRUD.get_messages(
            db, thread_id, skip=skip, limit=limit, before=before
        )

        # Get total count
        total_count = crud.ChatMessageCRUD.get_messages_count(db, thread_id)

        # Check if there are more messages
        has_more = (skip + len(messages)) < total_count

        return schemas.ChatMessagesListResponse(
            messages=messages, has_more=has_more, total_count=total_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages for thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/messages/{message_id}", response_model=schemas.ChatMessageResponse)
async def update_message(
    message_id: UUID, 
    update_data: schemas.ChatMessageUpdate, 
    db: Session = Depends(get_db)
):
    """Update a chat message"""
    try:
        updated_message = crud.ChatMessageCRUD.update_message(db, message_id, update_data.content)
        if not updated_message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update(
                {
                    "type": "message_updated",
                    "thread_id": str(updated_message.thread_id),
                    "message_id": str(message_id),
                    "content": update_data.content,
                    "edited_at": (
                        updated_message.edited_at.isoformat()
                        if updated_message.edited_at
                        else None
                    ),
                }
            )
        )

        logger.info(f"Updated message {message_id}")
        return updated_message

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update message {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Chat Notification Endpoints
@router.get("/notifications", response_model=List[schemas.ChatNotificationResponse])
async def get_notifications(
    thread_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = False,
    db: Session = Depends(get_db),
):
    """Get chat notifications"""
    try:
        notifications = crud.ChatNotificationCRUD.get_notifications(
            db,
            thread_id=thread_id,
            skip=skip,
            limit=limit,
            unread_only=unread_only,
        )
        return notifications

    except Exception as e:
        logger.error(f"Failed to get notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: UUID, db: Session = Depends(get_db)):
    """Mark a notification as read"""
    try:
        success = crud.ChatNotificationCRUD.mark_notification_read(db, notification_id)
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found")

        logger.info(f"Marked notification {notification_id} as read")
        return {"message": "Notification marked as read"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification {notification_id} as read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/{thread_id}/notifications/read")
async def mark_thread_notifications_read(
    thread_id: UUID, db: Session = Depends(get_db)
):
    """Mark all notifications in a thread as read"""
    try:
        # Verify thread exists
        thread = crud.ChatThreadCRUD.get_thread(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        updated_count = crud.ChatNotificationCRUD.mark_thread_notifications_read(
            db, thread_id
        )

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update(
                {
                    "type": "notifications_read",
                    "thread_id": str(thread_id),
                    "count": updated_count,
                }
            )
        )

        logger.info(
            f"Marked {updated_count} notifications as read for thread {thread_id}"
        )
        return {"message": f"Marked {updated_count} notifications as read"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to mark thread {thread_id} notifications as read: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications/unread-count")
async def get_unread_notifications_count(
    thread_id: Optional[UUID] = None, db: Session = Depends(get_db)
):
    """Get count of unread notifications"""
    try:
        count = crud.ChatNotificationCRUD.get_unread_count(db, thread_id)
        return {"unread_count": count}

    except Exception as e:
        logger.error(f"Failed to get unread notifications count: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Message Search Endpoint
@router.get("/search")
async def search_messages(
    q: str = Query(..., description="Search query"),
    role: Optional[str] = Query(None, description="Filter by message role"),
    message_type: Optional[str] = Query(None, description="Filter by message type"),
    date_range: Optional[str] = Query(None, description="Filter by date range"),
    thread_ids: Optional[str] = Query(None, description="Comma-separated thread IDs"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
):
    """Search messages across threads with full-text search and filters"""
    import time
    start_time = time.time()
    
    try:
        # Parse thread IDs if provided
        thread_id_list = []
        if thread_ids:
            try:
                thread_id_list = [UUID(tid.strip()) for tid in thread_ids.split(",") if tid.strip()]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid thread ID format: {str(e)}")

        # Parse date range
        date_filter = None
        if date_range:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            
            if date_range == "today":
                date_filter = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_range == "week":
                date_filter = now - timedelta(days=7)
            elif date_range == "month":
                date_filter = now - timedelta(days=30)
            elif date_range == "3months":
                date_filter = now - timedelta(days=90)

        # Perform search using database
        results = crud.ChatMessageCRUD.search_messages(
            db=db,
            query=q,
            role=role,
            message_type=message_type,
            date_filter=date_filter,
            thread_ids=thread_id_list,
            limit=limit,
            offset=offset,
        )

        # Get thread titles for results
        thread_titles = {}
        if results:
            unique_thread_ids = list(set(result.thread_id for result in results))
            threads = crud.ChatThreadCRUD.get_threads_by_ids(db, unique_thread_ids)
            thread_titles = {thread.id: thread.title for thread in threads}

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "thread_id": result.thread_id,
                "role": result.role.value,
                "content": result.content,
                "message_type": result.message_type.value,
                "metadata": result.metadata,
                "created_at": result.created_at.isoformat(),
                "threadTitle": thread_titles.get(result.thread_id, "Unknown Thread"),
            })

        # Get total count for pagination (simplified for now)
        total_count = len(formatted_results)
        
        end_time = time.time()
        took_ms = int((end_time - start_time) * 1000)

        logger.info(f"Search completed for query '{q}': {len(formatted_results)} results in {took_ms}ms")

        return {
            "results": formatted_results,
            "total": total_count,
            "took_ms": took_ms,
            "query": q,
            "filters": {
                "role": role,
                "message_type": message_type,
                "date_range": date_range,
                "thread_ids": thread_ids,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
