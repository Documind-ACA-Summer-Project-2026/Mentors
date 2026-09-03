import os
import numpy as np
import psycopg2
from psycopg2.extras import execute_values

class VectorStore:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            print("WARNING: DATABASE_URL not set in environment variables.")

    def _get_connection(self):
        if not self.db_url:
            raise ValueError("DATABASE_URL is not set. Please configure it in .env file.")
        conn = psycopg2.connect(self.db_url)
        try:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO documind, public;")
        except Exception as e:
            conn.close()
            raise e
        return conn

    def add(self, text, embedding, metadata):
        """
        Add a chunk and its vector to the document_chunks table.
        metadata must contain 'doc_id' and 'user_id'.
        """
        doc_id = metadata.get("doc_id")
        user_id = metadata.get("user_id")
        if not doc_id:
            raise ValueError("Metadata must contain 'doc_id'")

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_chunks (doc_id, user_id, chunk_text, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    """,
                    (doc_id, user_id, text, list(embedding))
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def add_chunks_batch(self, chunks, embeddings, doc_id, user_id):
        """
        Add a list of chunks and embeddings in a single transaction.
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                data = [
                    (doc_id, user_id, chunk, list(emb))
                    for chunk, emb in zip(chunks, embeddings)
                ]
                execute_values(
                    cur,
                    """
                    INSERT INTO document_chunks (doc_id, user_id, chunk_text, embedding)
                    VALUES %s
                    """,
                    data,
                    template="(%s, %s, %s, %s::vector)"
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def hybrid_search(self, query_embedding, query_text, user_id=None, k=5):
        """
        Perform hybrid search using pgvector (semantic search) and PostgreSQL FTS (keyword search),
        combining the ranks using Reciprocal Rank Fusion (RRF).
        Returns list of (score, chunk_text).
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # We filter by user_id OR public documents (user_id IS NULL)
                # Reciprocal Rank Fusion query
                query = """
                WITH semantic_search AS (
                    SELECT id, chunk_text,
                           ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
                    FROM document_chunks
                    WHERE (user_id = %s OR user_id IS NULL)
                    LIMIT 20
                ),
                keyword_search AS (
                    SELECT id, chunk_text,
                           ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', chunk_text), plainto_tsquery('english', %s)) DESC) AS rank
                    FROM document_chunks
                    WHERE (user_id = %s OR user_id IS NULL) 
                      AND to_tsvector('english', chunk_text) @@ plainto_tsquery('english', %s)
                    LIMIT 20
                )
                SELECT 
                    COALESCE(s.chunk_text, k.chunk_text) AS chunk_text,
                    (1.0 / (60.0 + COALESCE(s.rank, 999))) + (1.0 / (60.0 + COALESCE(k.rank, 999))) AS rrf_score
                FROM semantic_search s
                FULL OUTER JOIN keyword_search k ON s.id = k.id
                ORDER BY rrf_score DESC
                LIMIT %s;
                """
                cur.execute(
                    query,
                    (
                        list(query_embedding),
                        user_id,
                        query_text,
                        user_id,
                        query_text,
                        k
                    )
                )
                rows = cur.fetchall()
                # Return list of (score, text) matching the original interface format
                return [(float(row[1]), row[0]) for row in rows]
        except Exception as e:
            print("Hybrid search failed:", e)
            # Fallback to purely semantic search if FTS syntax query fails or is empty
            try:
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT chunk_text, 1 - (embedding <=> %s::vector) AS similarity
                        FROM document_chunks
                        WHERE (user_id = %s OR user_id IS NULL)
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s;
                        """,
                        (list(query_embedding), user_id, list(query_embedding), k)
                    )
                    rows = cur.fetchall()
                    return [(float(row[1]), row[0]) for row in rows]
            except Exception as fallback_e:
                print("Semantic fallback search failed:", fallback_e)
                return []
        finally:
            conn.close()

    def delete_document(self, doc_id):
        """Remove all text chunks associated with a document ID"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_chunks WHERE doc_id = %s", (doc_id,))
            conn.commit()
            print(f"Deleted chunks for document {doc_id} from PostgreSQL")
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # Stub methods to maintain API compatibility
    def save(self, filepath=None):
        pass

    def load(self, filepath=None):
        return True