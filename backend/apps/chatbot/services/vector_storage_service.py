"""
Vector Storage Service

Handles PGVector operations for document embeddings and semantic search (RAG).
Uses the modern ``langchain_postgres`` PGEngine + PGVectorStore API.

Usage:
    from chatbot.services import VectorStorageService

    # Store document embeddings
    vector_ids = VectorStorageService.store_document_embeddings(
        document=doc,
        chunks=text_chunks,
        user=request.user
    )

    # Semantic search
    results = VectorStorageService.semantic_search(
        query="What is machine learning?",
        user=request.user,
        k=5
    )
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import threading

from django.conf import settings
from langchain_postgres import PGEngine, PGVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from ..models import UserDocument
from accounts.models import CustomUser

# text-embedding-3-small produces 1536-dimensional vectors
EMBEDDING_DIMENSION = 1536


class VectorStorageService:
    """Service for managing vector embeddings and semantic search via PGEngine + PGVectorStore."""

    # Singleton engine — shared across all requests in a process
    _engine: Optional[PGEngine] = None
    _engine_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_engine(cls) -> PGEngine:
        """
        Get or create the singleton PGEngine instance.

        PGEngine manages the SQLAlchemy connection pool. Reusing a single
        instance avoids opening a new pool on every request.

        Returns:
            PGEngine connected to ``settings.PGVECTOR_CONNECTION_STRING``
        """
        if cls._engine is None:
            with cls._engine_lock:
                # Double-checked locking
                if cls._engine is None:
                    cls._engine = PGEngine.from_connection_string(
                        url=settings.PGVECTOR_CONNECTION_STRING,
                    )
        return cls._engine

    @classmethod
    def _get_embedding_model(cls) -> OpenAIEmbeddings:
        """Return the default embedding model (text-embedding-3-small)."""
        return OpenAIEmbeddings(model="text-embedding-3-small")

    @classmethod
    def _get_vector_store(
        cls,
        table_name: str,
        embeddings: Optional[Any] = None,
    ) -> PGVectorStore:
        """
        Create a PGVectorStore backed by *table_name*.

        The table is auto-created on first use via ``init_vectorstore_table``
        (idempotent — safe to call every time).

        Args:
            table_name: PostgreSQL table name for the collection.
            embeddings: Embedding model override (default: text-embedding-3-small).

        Returns:
            A ready-to-use PGVectorStore instance.
        """
        engine = cls._get_engine()
        embedding_model = embeddings or cls._get_embedding_model()

        # Ensure the table exists (idempotent CREATE TABLE IF NOT EXISTS)
        engine.init_vectorstore_table(
            table_name=table_name,
            vector_size=EMBEDDING_DIMENSION,
        )

        return PGVectorStore.create_sync(
            engine=engine,
            table_name=table_name,
            embedding_service=embedding_model,
        )

    # ------------------------------------------------------------------ #
    #  Collection / table naming helpers                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_user_collection_name(user: CustomUser) -> str:
        """
        Standardised table name for a user's documents.

        Args:
            user: The user

        Returns:
            Table name string

        Example:
            >>> VectorStorageService.create_user_collection_name(user)
            'user_123_documents'
        """
        return f"user_{user.id}_documents"

    @staticmethod
    def create_session_collection_name(session_id: UUID) -> str:
        """
        Standardised table name for a session's context.

        Args:
            session_id: Chat session ID

        Returns:
            Table name string

        Example:
            >>> VectorStorageService.create_session_collection_name(session.id)
            'session_abc123_context'
        """
        return f"session_{session_id}_context"

    # ------------------------------------------------------------------ #
    #  Write operations                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def store_document_embeddings(
        document: UserDocument,
        chunks: List[str],
        user: CustomUser,
        collection_name: Optional[str] = None,
        embeddings: Optional[Any] = None,
    ) -> List[str]:
        """
        Store document chunks as vector embeddings.

        Args:
            document: UserDocument instance.
            chunks: Text chunks to embed.
            user: Owning user.
            collection_name: Custom table name (default: per-user table).
            embeddings: Custom embedding model override.

        Returns:
            List of stored vector IDs.

        Example:
            vector_ids = VectorStorageService.store_document_embeddings(
                document=doc,
                chunks=text_chunks,
                user=request.user,
            )
        """
        table_name = (
            collection_name or VectorStorageService.create_user_collection_name(user)
        )

        vector_store = VectorStorageService._get_vector_store(
            table_name=table_name, embeddings=embeddings,
        )

        metadata = document.get_vector_metadata()

        vector_ids = vector_store.add_texts(
            texts=chunks,
            metadatas=[metadata] * len(chunks),
        )

        document.mark_processing_completed(
            collection_name=table_name,
            vector_ids=vector_ids,
            chunk_count=len(chunks),
            collection_metadata={"user_id": str(user.id)},
            vector_metadata=metadata,
        )

        return vector_ids

    @staticmethod
    def reindex_document(
        document: UserDocument,
        new_chunks: List[str],
        user: CustomUser,
    ) -> List[str]:
        """
        Reindex a document (delete old embeddings, then store new ones).

        Args:
            document: UserDocument to reindex.
            new_chunks: New text chunks.
            user: Document owner.

        Returns:
            New vector IDs.

        Example:
            new_chunks = splitter.split_text(text)
            VectorStorageService.reindex_document(doc, new_chunks, user)
        """
        VectorStorageService.delete_document_embeddings(document)
        return VectorStorageService.store_document_embeddings(
            document=document, chunks=new_chunks, user=user,
        )

    @staticmethod
    def delete_document_embeddings(document: UserDocument) -> None:
        """
        Delete all embeddings for a document.

        Args:
            document: UserDocument whose embeddings should be removed.

        Example:
            VectorStorageService.delete_document_embeddings(doc)
        """
        if not document.has_embeddings:
            return

        vector_store = VectorStorageService._get_vector_store(
            document.vector_collection_name,
        )

        # Batch-delete all vector IDs in one call
        vector_store.delete(ids=document.vector_store_ids)

        # Clear metadata on the model
        document.vector_collection_name = ""
        document.vector_store_ids = []
        document.chunk_count = 0
        document.save()

    # ------------------------------------------------------------------ #
    #  Search operations                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def semantic_search(
        query: str,
        user: CustomUser,
        k: int = 5,
        collection_name: Optional[str] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        embeddings: Optional[Any] = None,
    ) -> List[Document]:
        """
        Semantic similarity search over a user's documents.

        Args:
            query: Natural-language search query.
            user: User whose documents to search.
            k: Number of results.
            collection_name: Specific table (default: user table).
            filter_dict: Additional metadata filters.
            embeddings: Custom embedding model.

        Returns:
            List of matching Document objects.

        Example:
            results = VectorStorageService.semantic_search(
                query="What is machine learning?",
                user=request.user,
                k=5,
            )
        """
        table_name = (
            collection_name or VectorStorageService.create_user_collection_name(user)
        )

        vector_store = VectorStorageService._get_vector_store(
            table_name=table_name, embeddings=embeddings,
        )

        # Base filter: only this user's documents
        base_filter: Dict[str, Any] = {"user_id": {"$eq": str(user.id)}}
        search_filter = (
            {"$and": [base_filter, filter_dict]} if filter_dict else base_filter
        )

        return vector_store.similarity_search(query=query, k=k, filter=search_filter)

    @staticmethod
    def semantic_search_with_scores(
        query: str,
        user: CustomUser,
        k: int = 5,
        collection_name: Optional[str] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[tuple[Document, float]]:
        """
        Semantic search with relevance scores.

        Args:
            query: Natural-language search query.
            user: User whose documents to search.
            k: Number of results.
            collection_name: Specific table (default: user table).
            filter_dict: Additional metadata filters.

        Returns:
            List of (Document, score) tuples ordered by relevance.

        Example:
            for doc, score in VectorStorageService.semantic_search_with_scores(
                query="AI research", user=request.user, k=10,
            ):
                print(f"Score: {score:.3f}  {doc.page_content[:100]}")
        """
        table_name = (
            collection_name or VectorStorageService.create_user_collection_name(user)
        )

        vector_store = VectorStorageService._get_vector_store(table_name=table_name)

        base_filter: Dict[str, Any] = {"user_id": {"$eq": str(user.id)}}
        search_filter = (
            {"$and": [base_filter, filter_dict]} if filter_dict else base_filter
        )

        return vector_store.similarity_search_with_score(
            query=query, k=k, filter=search_filter,
        )

    # ------------------------------------------------------------------ #
    #  Formatting & stats helpers                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def format_search_results_for_context(
        results: List[Document],
        max_context_length: Optional[int] = None,
    ) -> str:
        """
        Format search results into a context string suitable for LLM injection.

        Args:
            results: Documents from ``semantic_search()``.
            max_context_length: Truncate beyond this many characters.

        Returns:
            Formatted context string.

        Example:
            context = VectorStorageService.format_search_results_for_context(
                results, max_context_length=2000,
            )
        """
        context_parts = []

        for i, doc in enumerate(results, 1):
            source = doc.metadata.get("file_name", "Unknown")
            content = doc.page_content
            context_parts.append(f"[Source {i}: {source}]\n{content}\n")

        context = "\n".join(context_parts)

        if max_context_length and len(context) > max_context_length:
            context = context[:max_context_length] + "..."

        return context

    @staticmethod
    def get_user_storage_stats(user: CustomUser) -> Dict[str, Any]:
        """
        Aggregate storage statistics for a user.

        Args:
            user: The user

        Returns:
            Dict with total_documents, total_chunks, total_size_mb, etc.

        Example:
            stats = VectorStorageService.get_user_storage_stats(user)
        """
        user_docs = UserDocument.objects.filter(
            user=user, processing_status="completed",
        )

        total_docs = user_docs.count()
        total_chunks = sum(doc.chunk_count or 0 for doc in user_docs)
        total_size = sum(doc.file_size or 0 for doc in user_docs)

        collections = {
            doc.vector_collection_name
            for doc in user_docs
            if doc.vector_collection_name
        }

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "collection_count": len(collections),
            "collections": list(collections),
        }

    @staticmethod
    def get_collection_documents(
        collection_name: str,
        user: Optional[CustomUser] = None,
    ) -> List[UserDocument]:
        """
        Get all UserDocument records belonging to a collection/table.

        Args:
            collection_name: Table name
            user: Optional user filter

        Returns:
            List of UserDocument instances
        """
        return UserDocument.get_documents_in_collection(
            collection_name=collection_name, user=user,
        )
