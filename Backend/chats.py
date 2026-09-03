import uuid
import psycopg2
import psycopg2.extras
import logging
from fastapi import APIRouter, Depends, HTTPException

from database import get_db_connection
from auth import get_current_user
from schemas import CreateChatRequest
from error_handlers import (
    ResourceNotFoundError, DatabaseError, ValidationError,
    handle_database_error, log_error
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chats", tags=["chats"])

@router.get("")
def get_chats(current_user: dict = Depends(get_current_user)):
    """Retrieve all chats for the current user."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, title, created_at FROM chats WHERE user_id = %s ORDER BY created_at DESC", (current_user["id"],))
                rows = cursor.fetchall()
                logger.info(f"Retrieved {len(rows)} chats for user {current_user['id']}")
                return [dict(r) for r in rows]
    except psycopg2.Error as e:
        log_error(e, "get_chats database")
        raise handle_database_error(e)
    except Exception as e:
        log_error(e, "get_chats")
        raise DatabaseError("Failed to retrieve chats")

@router.post("")
def create_chat(req: CreateChatRequest, current_user: dict = Depends(get_current_user)):
    """Create a new chat."""
    try:
        # Validate input
        if not req.title or len(req.title.strip()) == 0:
            raise ValidationError("Chat title is required", "title")
        if len(req.title) > 255:
            raise ValidationError("Chat title is too long (max 255 characters)", "title")
        
        chat_id = str(uuid.uuid4())
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("INSERT INTO chats (id, title, user_id) VALUES (%s, %s, %s)", (chat_id, req.title, current_user["id"]))
                conn.commit()
            logger.info(f"Chat created: {chat_id} for user {current_user['id']}")
            return {"id": chat_id, "title": req.title}
        except psycopg2.Error as e:
            log_error(e, "create_chat database")
            raise handle_database_error(e)
    except ValidationError:
        raise
    except Exception as e:
        log_error(e, "create_chat")
        raise DatabaseError("Failed to create chat")

@router.delete("/{chat_id}")
def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a chat by ID."""
    try:
        # Validate input
        if not chat_id or chat_id.strip() == "":
            raise ValidationError("Chat ID is required", "chat_id")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Verify user owns this chat
                    cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (chat_id, current_user["id"]))
                    if not cursor.fetchone():
                        raise ResourceNotFoundError("Chat", chat_id)
                    
                    # Cascade delete deletes messages from the database
                    cursor.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
                conn.commit()
            logger.info(f"Chat deleted: {chat_id} for user {current_user['id']}")
            return {"status": "success"}
        except psycopg2.Error as e:
            log_error(e, "delete_chat database")
            raise handle_database_error(e)
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "delete_chat")
        raise DatabaseError("Failed to delete chat")

@router.get("/{chat_id}/messages")
def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve all messages for a specific chat."""
    try:
        # Validate input
        if not chat_id or chat_id.strip() == "":
            raise ValidationError("Chat ID is required", "chat_id")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    # Verify user owns this chat
                    cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (chat_id, current_user["id"]))
                    if not cursor.fetchone():
                        raise ResourceNotFoundError("Chat", chat_id)
                    
                    # Retrieve messages
                    cursor.execute("SELECT id, from_user, text, timestamp FROM messages WHERE chat_id = %s ORDER BY timestamp ASC", (chat_id,))
                    rows = cursor.fetchall()
                    logger.info(f"Retrieved {len(rows)} messages for chat {chat_id}")
                    return [dict(r) for r in rows]
        except psycopg2.Error as e:
            log_error(e, "get_messages database")
            raise handle_database_error(e)
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "get_messages")
        raise DatabaseError("Failed to retrieve messages")
