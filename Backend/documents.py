import os
import uuid
import shutil
import json
import psycopg2
import psycopg2.extras
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from database import get_db_connection
from auth import get_current_user
from schemas import ChatRequest
from error_handlers import (
    ResourceNotFoundError, DatabaseError, ValidationError,
    ExternalServiceError, handle_database_error, handle_file_error,
    handle_gemini_error, log_error
)

# RAG module imports
from rag.document import PDFLoader
from rag.chunker import TextChunker
from rag.embeddings import GeminiEmbedding
from rag.vector_store import VectorStore
from rag.retriever import Retriever
from rag.prompt import PromptBuilder
from rag.llm import LLM

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

# Initialize global RAG components
store = VectorStore()
embedding = GeminiEmbedding()
retriever = Retriever(embedding, store)

@router.get("/documents")
def get_documents(current_user: dict = Depends(get_current_user)):
    """Retrieve all documents for the current user."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, filename, upload_time FROM documents WHERE user_id = %s ORDER BY upload_time DESC", (current_user["id"],))
                rows = cursor.fetchall()
                logger.info(f"Retrieved {len(rows)} documents for user {current_user['id']}")
                return [dict(r) for r in rows]
    except psycopg2.Error as e:
        log_error(e, "get_documents database")
        raise handle_database_error(e)
    except Exception as e:
        log_error(e, "get_documents")
        raise DatabaseError("Failed to retrieve documents")

@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload and process a PDF document."""
    file_path = None
    doc_id = None
    
    try:
        # Validate file
        if not file.filename:
            raise ValidationError("Filename is required", "file")
        if not file.filename.lower().endswith('.pdf'):
            raise ValidationError("Only PDF files are allowed", "file")
        
        # Limit file size to 50MB
        MAX_FILE_SIZE = 50 * 1024 * 1024
        if file.size and file.size > MAX_FILE_SIZE:
            raise ValidationError("File size exceeds 50MB limit", "file")
        
        doc_id = str(uuid.uuid4())
        upload_dir = "/tmp" if os.environ.get("VERCEL") else "data/documents"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{doc_id}.pdf")
        
        # Save uploaded file
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            logger.info(f"File saved: {file_path} for user {current_user['id']}")
        except IOError as e:
            log_error(e, "upload_document file save")
            raise handle_file_error(e)
        
        # Process PDF
        try:
            loader = PDFLoader()
            document = loader.load(file_path)
            
            chunker = TextChunker()
            chunks = chunker.chunk(document)
            
            if not chunks or len(chunks) == 0:
                raise ValidationError("PDF file is empty or could not be parsed")
            
            logger.info(f"PDF chunked into {len(chunks)} parts")
        except Exception as e:
            log_error(e, "upload_document pdf processing")
            raise ExternalServiceError("PDF Processing", str(e))
        
        # Generate embeddings
        try:
            embedding_model = GeminiEmbedding()
            embeddings = []
            for chunk in chunks:
                vector = embedding_model.embed(chunk)
                embeddings.append(vector)
            logger.info(f"Generated {len(embeddings)} embeddings")
        except Exception as e:
            log_error(e, "upload_document embeddings")
            raise handle_gemini_error(e)
        
        # Insert document metadata
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO documents (id, filename, user_id) VALUES (%s, %s, %s)",
                        (doc_id, file.filename, current_user["id"])
                    )
                conn.commit()
            logger.info(f"Document metadata inserted: {doc_id}")
        except psycopg2.Error as e:
            log_error(e, "upload_document insert metadata")
            raise handle_database_error(e)
        
        # Index chunks in vector store
        try:
            store.add_chunks_batch(chunks, embeddings, doc_id, current_user["id"])
            logger.info(f"Document indexed successfully: {doc_id}")
        except Exception as e:
            log_error(e, "upload_document chunk indexing")
            # Clean up the document record if chunk indexing fails
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                    conn.commit()
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up document record: {cleanup_error}")
            
            raise ExternalServiceError("Vector Store", str(e))
        
        return {"id": doc_id, "filename": file.filename}
    
    except (ValidationError, ExternalServiceError):
        # Clean up file if something went wrong
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to clean up file: {e}")
        raise
    except Exception as e:
        # Clean up file on any error
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up file: {cleanup_error}")
        log_error(e, "upload_document")
        raise DatabaseError("Failed to process and index PDF")

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a document and its associated data."""
    try:
        # Validate input
        if not doc_id or doc_id.strip() == "":
            raise ValidationError("Document ID is required", "doc_id")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    # Verify user owns this document
                    cursor.execute("SELECT id FROM documents WHERE id = %s AND user_id = %s", (doc_id, current_user["id"]))
                    doc = cursor.fetchone()
                    
                    if not doc:
                        raise ResourceNotFoundError("Document", doc_id)
        except psycopg2.Error as e:
            log_error(e, "delete_document verify ownership")
            raise handle_database_error(e)
        
        # Remove from vector store
        try:
            store.delete_document(doc_id)
            logger.info(f"Document removed from vector store: {doc_id}")
        except Exception as e:
            logger.warning(f"Failed to remove document from vector store: {e}")
            # Don't fail the entire delete operation if vector store removal fails
        
        # Remove uploaded file
        upload_dir = "/tmp" if os.environ.get("VERCEL") else "data/documents"
        file_path = os.path.join(upload_dir, f"{doc_id}.pdf")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            except OSError as e:
                log_error(e, "delete_document file removal")
                logger.warning(f"Failed to delete file: {file_path}")
                # Don't fail the entire delete operation if file deletion fails
        
        # Delete from database
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                conn.commit()
            logger.info(f"Document deleted from database: {doc_id}")
        except psycopg2.Error as e:
            log_error(e, "delete_document database deletion")
            raise handle_database_error(e)
        
        return {"status": "success"}
    
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "delete_document")
        raise DatabaseError("Failed to delete document")

def detect_intent(message: str) -> str:
    """Detect intent of user message using LLM."""
    prompt = f"""
Classify the user's message into exactly one of these categories:
- 'GREETING': A greeting only, such as 'hello' or 'good morning'.
- 'SMALL_TALK': Simple social conversation with no factual question, such as 'how are you?'.
- 'DOCUMENT_INQUIRY': Every factual or informational question, including questions
  about uploaded documents and general-knowledge questions. Ambiguous messages
  must also be classified as 'DOCUMENT_INQUIRY' so they can be checked against
  the user's documents.

User message: "{message}"

Respond with ONLY one exact category name.
"""
    try:
        response = LLM().generate(prompt).strip().upper()
        if response in {"GREETING", "SMALL_TALK", "DOCUMENT_INQUIRY"}:
            logger.info(f"Query intent: {response}")
            return response
        logger.warning(f"Unknown intent response {response!r}; treating as DOCUMENT_INQUIRY")
        return "DOCUMENT_INQUIRY"
    except Exception as e:
        logger.warning(f"Intent detection failed, defaulting to DOCUMENT_INQUIRY: {e}")
        return "DOCUMENT_INQUIRY"

async def event_generator(chat_id: str, message: str, user_id: int):
    """Stream chat responses with error handling."""
    try:
        intent = detect_intent(message)

        if intent in {"GREETING", "SMALL_TALK"}:
            direct_response = "How may I help you?"
            prompt = None
            logger.info(f"Returning fixed response for {intent}")
        else:
            # Every factual or ambiguous question must use document context.
            direct_response = None
            prompt = None
            contexts = None
            
        if intent == "DOCUMENT_INQUIRY":
            # Retrieve top-5 contexts using hybrid semantic and keyword search.
            try:
                contexts = retriever.retrieve(message, user_id=user_id, top_k=5)
                prompt = PromptBuilder().build(message, contexts)
                logger.info(f"Retrieved {len(contexts)} contexts for document inquiry")
            except Exception as e:
                log_error(e, "event_generator retrieval")
                yield f"data: {json.dumps({'error': 'Failed to retrieve document context. ' + str(e)})}\n\n"
                return

        if prompt is None and direct_response is None:
            logger.error(f"Unable to build prompt for intent {intent}")
            yield f"data: {json.dumps({'error': 'Unable to process the request'})}\n\n"
            return

        accumulated_response = ""
        try:
            if direct_response is not None:
                accumulated_response = direct_response
                yield f"data: {json.dumps({'text': direct_response})}\n\n"
            else:
                llm = LLM()
                for chunk in llm.generate_stream(prompt):
                    accumulated_response += chunk
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log_error(e, "event_generator llm streaming")
            logger.error(f"LLM stream generation failed: {e}")
            yield f"data: {json.dumps({'error': f'LLM error: {str(e)}' })}\n\n"
            return

        # Save messages to DB on completion
        user_msg_id = str(uuid.uuid4())
        bot_msg_id = str(uuid.uuid4())
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, TRUE, %s)",
                        (user_msg_id, chat_id, message)
                    )
                    cur.execute(
                        "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, FALSE, %s)",
                        (bot_msg_id, chat_id, accumulated_response)
                    )
                conn.commit()
            logger.info(f"Chat messages saved for chat {chat_id}")
        except psycopg2.Error as db_e:
            log_error(db_e, "event_generator save messages")
            logger.error(f"Failed to save streamed chat messages to DB: {db_e}")
            # Don't fail the entire stream if DB save fails - response was already sent to user
        
        yield "data: [DONE]\n\n"
    
    except Exception as e:
        log_error(e, "event_generator general")
        logger.error(f"Unexpected error in event generator: {e}")
        yield f"data: {json.dumps({'error': 'An unexpected error occurred'})}\n\n"

@router.post("/chat")
def chat_query(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Send a message and get streaming response."""
    try:
        # Validate input
        if not req.chat_id or req.chat_id.strip() == "":
            raise ValidationError("Chat ID is required", "chat_id")
        if not req.message or req.message.strip() == "":
            raise ValidationError("Message is required", "message")
        if len(req.message) > 5000:
            raise ValidationError("Message is too long (max 5000 characters)", "message")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Verify user owns this chat
                    cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (req.chat_id, current_user["id"]))
                    if not cursor.fetchone():
                        raise ResourceNotFoundError("Chat", req.chat_id)
        except psycopg2.Error as e:
            log_error(e, "chat_query verify ownership")
            raise handle_database_error(e)
        
        logger.info(f"Starting chat query for chat {req.chat_id}, user {current_user['id']}")
        return StreamingResponse(
            event_generator(req.chat_id, req.message, current_user["id"]),
            media_type="text/event-stream"
        )
    
    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        log_error(e, "chat_query")
        raise DatabaseError("Failed to process chat query")
