class Retriever:

    def __init__(self,
                 embedding_model,
                 vector_store):

        self.embedding_model = embedding_model
        self.vector_store = vector_store

    def retrieve(self,
                 question,
                 user_id=None,
                 top_k=5):

        query_embedding = self.embedding_model.embed(question)

        # Call the new hybrid_search on vector_store passing both vector and text query
        return self.vector_store.hybrid_search(
            query_embedding=query_embedding,
            query_text=question,
            user_id=user_id,
            k=top_k
        )