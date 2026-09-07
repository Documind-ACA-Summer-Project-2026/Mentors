CREATE SCHEMA IF NOT EXISTS documind;

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;


-- Drop tables if they exist (for migration / resetting)
-- DROP TABLE IF EXISTS document_chunks CASCADE;
-- DROP TABLE IF EXISTS messages CASCADE;
-- DROP TABLE IF EXISTS chats CASCADE;
-- DROP TABLE IF EXISTS documents CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- Create Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    google_sub VARCHAR(255) UNIQUE,
    is_verified BOOLEAN DEFAULT FALSE,
    otp_code VARCHAR(6),
    otp_expires_at TIMESTAMP
);

-- Create Documents table
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(255) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
);

-- Create Chats table
CREATE TABLE IF NOT EXISTS chats (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Messages table
CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(255) PRIMARY KEY,
    chat_id VARCHAR(255) REFERENCES chats(id) ON DELETE CASCADE,
    from_user BOOLEAN NOT NULL,
    text TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Document Chunks table for vector search
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(768) -- Gemini embeddings are 768-dimensional
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_chunks_user_id ON document_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id);

-- Create GIN index for full-text search on chunk_text
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON document_chunks USING gin(to_tsvector('english', chunk_text));
