from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Import modular router/db configurations
from database import init_db
from error_handlers import exception_handler, AppError, error_response
import auth
import chats
import documents

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Documind RAG API")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc)
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return await exception_handler(request, exc)

# Run schema initialization and migrations on startup
@app.on_event("startup")
def startup_event():
    try:
        init_db()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't block startup if DB init fails, but log it clearly


# Include Routers
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(documents.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)