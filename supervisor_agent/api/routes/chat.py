from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import asyncio

from supervisor_agent.db.database import get_db
from supervisor_agent.db import schemas, crud, models
from supervisor_agent.db.enums import ChatThreadStatus, MessageRole
from supervisor_agent.api.websocket import notify_chat_update
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# Chat Thread Endpoints
@router.post("/threads", response_model=schemas.ChatThreadResponse)
async def create_chat_thread(
    thread: schemas.ChatThreadCreate,
    request: Request,
    db: Session = Depends(get_db)
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
                "has_initial_message": bool(thread.initial_message)
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        crud.AuditLogCRUD.create_log(db, audit_data)

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update({
                "type": "thread_created",
                "thread_id": str(db_thread.id),
                "title": db_thread.title,
                "created_at": db_thread.created_at.isoformat()
            })
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
    db: Session = Depends(get_db)
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
                    last_message = messages[0].content[:100] + "..." if len(messages[0].content) > 100 else messages[0].content

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
                last_message_at=thread_data["last_message_at"]
            )
            threads.append(thread_response)

        # Get total count for pagination
        total_count = len(crud.ChatThreadCRUD.get_threads(db, limit=1000))  # Get rough count

        return schemas.ChatThreadListResponse(
            threads=threads,
            total_count=total_count
        )

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
            last_message = messages[0].content[:100] + "..." if len(messages[0].content) > 100 else messages[0].content
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
            last_message_at=last_message_at
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
    db: Session = Depends(get_db)
):
    """Update a chat thread"""
    try:
        updated_thread = crud.ChatThreadCRUD.update_thread(db, thread_id, thread_update)
        if not updated_thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update({
                "type": "thread_updated",
                "thread_id": str(thread_id),
                "title": updated_thread.title,
                "status": updated_thread.status.value
            })
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
            notify_chat_update({
                "type": "thread_deleted",
                "thread_id": str(thread_id)
            })
        )

        logger.info(f"Deleted chat thread {thread_id}")
        return {"message": "Chat thread deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete chat thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Chat Message Endpoints
@router.post("/threads/{thread_id}/messages", response_model=schemas.ChatMessageResponse)
async def send_message(
    thread_id: UUID,
    message: schemas.ChatMessageCreate,
    db: Session = Depends(get_db)
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
            notify_chat_update({
                "type": "message_sent",
                "thread_id": str(thread_id),
                "message_id": str(db_message.id),
                "content": message.content,
                "role": "user",
                "created_at": db_message.created_at.isoformat()
            })
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


@router.get("/threads/{thread_id}/messages", response_model=schemas.ChatMessagesListResponse)
async def get_messages(
    thread_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    before: Optional[UUID] = None,
    db: Session = Depends(get_db)
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
            messages=messages,
            has_more=has_more,
            total_count=total_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages for thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/messages/{message_id}", response_model=schemas.ChatMessageResponse)
async def update_message(
    message_id: UUID,
    content: str,
    db: Session = Depends(get_db)
):
    """Update a chat message"""
    try:
        updated_message = crud.ChatMessageCRUD.update_message(db, message_id, content)
        if not updated_message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update({
                "type": "message_updated",
                "thread_id": str(updated_message.thread_id),
                "message_id": str(message_id),
                "content": content,
                "edited_at": updated_message.edited_at.isoformat() if updated_message.edited_at else None
            })
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
    db: Session = Depends(get_db)
):
    """Get chat notifications"""
    try:
        notifications = crud.ChatNotificationCRUD.get_notifications(
            db, thread_id=thread_id, skip=skip, limit=limit, unread_only=unread_only
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
async def mark_thread_notifications_read(thread_id: UUID, db: Session = Depends(get_db)):
    """Mark all notifications in a thread as read"""
    try:
        # Verify thread exists
        thread = crud.ChatThreadCRUD.get_thread(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")

        updated_count = crud.ChatNotificationCRUD.mark_thread_notifications_read(db, thread_id)

        # Send WebSocket notification
        asyncio.create_task(
            notify_chat_update({
                "type": "notifications_read",
                "thread_id": str(thread_id),
                "count": updated_count
            })
        )

        logger.info(f"Marked {updated_count} notifications as read for thread {thread_id}")
        return {"message": f"Marked {updated_count} notifications as read"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark thread {thread_id} notifications as read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications/unread-count")
async def get_unread_notifications_count(
    thread_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """Get count of unread notifications"""
    try:
        count = crud.ChatNotificationCRUD.get_unread_count(db, thread_id)
        return {"unread_count": count}

    except Exception as e:
        logger.error(f"Failed to get unread notifications count: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))