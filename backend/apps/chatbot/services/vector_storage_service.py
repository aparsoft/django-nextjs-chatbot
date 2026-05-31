"""
Vector Storage Service

Handles PGVector operations for document embeddings and semantic search (RAG).
Implements October 2025 best practices with proper collection and metadata management.

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

from django.conf import settings
from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from ..models import UserDocument
from accounts.models import CustomUser


class VectorStorageService:
    """Service for managing vector embeddings and semantic search."""

    @staticmethod
    def _get_vector_store(
        collection_name: str, embeddings: Optional[Any] = None
    ) -> PGVector:
        """
        Get PGVector store instance for a collection.

        Args:
            collection_name: Name of the collection
            embeddings: Embedding model (defaults to OpenAI)

        Returns:
            Configured PGVector instance
        """
        embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-small")

        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=settings.PGVECTOR_CONNECTION_STRING,
            use_jsonb=True,
        )

        return vector_store

    @staticmethod
    def create_user_collection_name(user: CustomUser) -> str:
        """
        Create standardized collection name for user.

        Args:
            user: The user

        Returns:
            Collection name string

        Example:
            collection = VectorStorageService.create_user_collection_name(user)
            # Returns: "user_123_documents"
        """
        return f"user_{user.id}_documents"

    @staticmethod
    def create_session_collection_name(session_id: UUID) -> str:
        """
        Create collection name for a specific session.

        Args:
            session_id: Chat session ID

        Returns:
            Collection name string

        Example:
            collection = VectorStorageService.create_session_collection_name(
                session_id=session.id
            )
            # Returns: "session_abc123_context"
        """
        return f"session_{session_id}_context"

    @staticmethod
    def store_document_embeddings(
        document: UserDocument,
        chunks: List[str],
        user: CustomUser,
        collection_name: Optional[str] = None,
        embeddings: Optional[Any] = None,
    ) -> List[str]:
        """
        Store document chunks as embeddings.

        Args:
            document: UserDocument instance
            chunks: List of text chunks to embed
            user: User who owns the document
            collection_name: Custom collection name (optional)
            embeddings: Custom embedding model (optional)

        Returns:
            List of vector IDs

        Example:
            from langchain.text_splitter import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
            chunks = splitter.split_text(document_text)

            vector_ids = VectorStorageService.store_document_embeddings(
                document=doc,
                chunks=chunks,
                user=request.user
            )
        """
        # Use user collection if not specified
        collection_name = (
            collection_name or VectorStorageService.create_user_collection_name(user)
        )

        # Get vector store
        vector_store = VectorStorageService._get_vector_store(
            collection_name=collection_name, embeddings=embeddings
        )

        # Get metadata for all chunks
        metadata = document.get_vector_metadata()

        # Store chunks with metadata
        vector_ids = vector_store.add_texts(
            texts=chunks,
            metadatas=[metadata] * len(chunks),  # Same metadata for all chunks
        )

        # Update document record
        document.mark_processing_completed(
            collection_name=collection_name,
            vector_ids=vector_ids,
            chunk_count=len(chunks),
            collection_metadata={"user_id": str(user.id)},
            vector_metadata=metadata,
        )

        return vector_ids

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
        Perform semantic search on user's documents.

        Args:
            query: Search query
            user: User for filtering
            k: Number of results
            collection_name: Specific collection (optional)
            filter_dict: Additional metadata filters (optional)
            embeddings: Custom embedding model (optional)

        Returns:
            List of Document objects with content and metadata

        Example:
            # Search user's documents
            results = VectorStorageService.semantic_search(
                query="What is machine learning?",
                user=request.user,
                k=5
            )

            # Search with category filter
            results = VectorStorageService.semantic_search(
                query="Python tutorials",
                user=request.user,
                k=3,
                filter_dict={"category": {"$eq": "programming"}}
            )
        """
        # Use user collection if not specified
        collection_name = (
            collection_name or VectorStorageService.create_user_collection_name(user)
        )

        # Get vector store
        vector_store = VectorStorageService._get_vector_store(
            collection_name=collection_name, embeddings=embeddings
        )

        # Build filter
        base_filter = {"user_id": {"$eq": str(user.id)}}

        if filter_dict:
            # Combine filters
            search_filter = {"$and": [base_filter, filter_dict]}
        else:
            search_filter = base_filter

        # Perform search
        results = vector_store.similarity_search(query=query, k=k, filter=search_filter)

        return results

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
            query: Search query
            user: User for filtering
            k: Number of results
            collection_name: Specific collection (optional)
            filter_dict: Additional metadata filters (optional)

        Returns:
            List of (Document, score) tuples

        Example:
            results = VectorStorageService.semantic_search_with_scores(
                query="AI research",
                user=request.user,
                k=10
            )

            for doc, score in results:
                print(f"Score: {score}, Content: {doc.page_content[:100]}")
        """
        collection_name = (
            collection_name or VectorStorageService.create_user_collection_name(user)
        )

        vector_store = VectorStorageService._get_vector_store(collection_name)

        # Build filter
        base_filter = {"user_id": {"$eq": str(user.id)}}

        if filter_dict:
            search_filter = {"$and": [base_filter, filter_dict]}
        else:
            search_filter = base_filter

        results = vector_store.similarity_search_with_score(
            query=query, k=k, filter=search_filter
        )

        return results

    @staticmethod
    def delete_document_embeddings(document: UserDocument) -> None:
        """
        Delete embeddings for a document.

        Args:
            document: UserDocument to delete embeddings for

        Example:
            VectorStorageService.delete_document_embeddings(doc)
        """
        if not document.has_embeddings:
            return

        vector_store = VectorStorageService._get_vector_store(
            document.vector_collection_name
        )

        # Delete by IDs
        for vector_id in document.vector_store_ids:
            vector_store.delete([vector_id])

        # Clear document metadata
        document.vector_collection_name = ""
        document.vector_store_ids = []
        document.chunk_count = 0
        document.save()

    @staticmethod
    def get_collection_documents(
        collection_name: str, user: Optional[CustomUser] = None
    ) -> List[UserDocument]:
        """
        Get all documents in a collection.

        Args:
            collection_name: Collection name
            user: Optional user filter

        Returns:
            List of UserDocument instances

        Example:
            docs = VectorStorageService.get_collection_documents(
                collection_name="user_123_documents",
                user=request.user
            )
        """
        return UserDocument.get_documents_in_collection(
            collection_name=collection_name, user=user
        )

    @staticmethod
    def format_search_results_for_context(
        results: List[Document], max_context_length: Optional[int] = None
    ) -> str:
        """
        Format search results into context string for LLM.

        Args:
            results: Search results
            max_context_length: Max characters (optional)

        Returns:
            Formatted context string

        Example:
            results = VectorStorageService.semantic_search(...)
            context = VectorStorageService.format_search_results_for_context(
                results,
                max_context_length=2000
            )

            # Use in prompt
            system_msg = f"Context:\n{context}\n\nQuestion: {query}"
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
        Get storage statistics for user's documents.

        Args:
            user: The user

        Returns:
            Dict with storage stats

        Example:
            stats = VectorStorageService.get_user_storage_stats(user)
            print(f"Total chunks: {stats['total_chunks']}")
        """
        user_docs = UserDocument.objects.filter(
            user=user, processing_status="completed"
        )

        total_docs = user_docs.count()
        total_chunks = sum(doc.chunk_count or 0 for doc in user_docs)
        total_size = sum(doc.file_size or 0 for doc in user_docs)

        collections = set()
        for doc in user_docs:
            if doc.vector_collection_name:
                collections.add(doc.vector_collection_name)

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "collection_count": len(collections),
            "collections": list(collections),
        }

    @staticmethod
    def reindex_document(
        document: UserDocument, new_chunks: List[str], user: CustomUser
    ) -> List[str]:
        """
        Reindex a document (delete old + create new embeddings).

        Args:
            document: UserDocument to reindex
            new_chunks: New text chunks
            user: Document owner

        Returns:
            New vector IDs

        Example:
            # Reprocess with different chunk size
            new_chunks = different_splitter.split_text(text)
            VectorStorageService.reindex_document(doc, new_chunks, user)
        """
        # Delete old embeddings
        VectorStorageService.delete_document_embeddings(document)

        # Create new embeddings
        vector_ids = VectorStorageService.store_document_embeddings(
            document=document, chunks=new_chunks, user=user
        )

        return vector_ids
