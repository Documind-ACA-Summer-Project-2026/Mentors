import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
import logging
from config import DATABASE_URL
from error_handlers import DatabaseError, handle_database_error

logger = logging.getLogger(__name__)

# Initialize ThreadedConnectionPool for fast connection reuse and to prevent leaks
db_pool = None
MAX_RETRIES = 3
CONNECTION_TIMEOUT = 10

def init_db_pool():
    global db_pool
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not configured. Database operations will fail.")
        return False
    try:
        db_pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=15,
            dsn=DATABASE_URL,
            connect_timeout=CONNECTION_TIMEOUT
        )
        logger.info("Database connection pool initialized successfully.")
        return True
    except psycopg2.OperationalError as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error initializing database pool: {e}")
        return False

# Run pool initialization immediately
pool_initialized = init_db_pool()

@contextmanager
def get_db_connection():
    """Get a database connection with proper error handling and retry logic."""
    global db_pool
    
    if not DATABASE_URL:
        raise DatabaseError("DATABASE_URL environment variable is not configured. Please set it in Backend/.env")
    
    # Try to get connection from pool or create a direct connection
    conn = None
    try:
        if db_pool:
            try:
                conn = db_pool.getconn()
            except psycopg2.pool.PoolError:
                logger.error("Database connection pool exhausted. Attempting direct connection.")
                conn = None
        
        # Fallback to direct connection if pool is unavailable
        if not conn:
            for attempt in range(MAX_RETRIES):
                try:
                    conn = psycopg2.connect(DATABASE_URL, connect_timeout=CONNECTION_TIMEOUT)
                    break
                except psycopg2.OperationalError as e:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Connection attempt {attempt + 1} failed, retrying...")
                        continue
                    else:
                        raise
        
        # Verify connection is working
        with conn.cursor() as cursor:
            cursor.execute("SET search_path TO documind, public;")
            cursor.execute("SELECT 1")  # Test query
        
        yield conn
        conn.commit()
        
    except psycopg2.OperationalError as e:
        if conn:
            conn.rollback()
        logger.error(f"Database connection error: {e}")
        raise handle_database_error(e)
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise handle_database_error(e)
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected database error: {e}")
        raise DatabaseError(f"Unexpected database error: {str(e)}")
    finally:
        if conn and db_pool:
            try:
                db_pool.putconn(conn)
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
                if conn:
                    conn.close()
        elif conn:
            conn.close()

def init_db():
    """Initialize database schema and run migrations with comprehensive error handling."""
    if not DATABASE_URL:
        logger.warning("DATABASE_URL is not set. Skipping schema initialization.")
        return
    
    try:
        logger.info("Initializing PostgreSQL database...")
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        
        if not os.path.exists(schema_path):
            logger.error(f"schema.sql not found at {schema_path}")
            return
            
        try:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
        except IOError as e:
            logger.error(f"Failed to read schema.sql: {e}")
            return
        
        if not schema_sql or not schema_sql.strip():
            logger.error("schema.sql is empty")
            return
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Execute main schema
                    cursor.execute(schema_sql)
                    
                    # Schema migrations for existing tables
                    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;")
                    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code VARCHAR(6);")
                    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMP;")
                    cursor.execute("UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL;")
                conn.commit()
            logger.info("Database schema and migrations initialized successfully.")
        except psycopg2.Error as e:
            logger.error(f"Database error during schema initialization: {e}")
            # Don't re-raise here - let the app continue
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
