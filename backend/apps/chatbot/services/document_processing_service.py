"""
Document Processing Service

Handles file upload processing, text extraction, chunking, and embedding creation.
Designed to be called from Celery tasks for asynchronous processing.

Usage:
    from chatbot.services import DocumentProcessingService

    # Process uploaded document
    DocumentProcessingService.process_document(
        document_id=doc.id,
        user_id=user.id
    )
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import mimetypes
import os

from django.core.files.uploadedfile import UploadedFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
)

from ..models import UserDocument
from accounts.models import CustomUser
from ..services.vector_storage_service import VectorStorageService


class DocumentProcessingService:
    """Service for processing uploaded documents."""

    # Supported file types
    SUPPORTED_TYPES = {
        "application/pdf": "pdf",
        "text/plain": "txt",
        "text/markdown": "md",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
    }

    @staticmethod
    def create_document_record(
        user: CustomUser,
        uploaded_file: UploadedFile,
        chat_session_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UserDocument:
        """
        Create initial document record from uploaded file.

        Args:
            user: User uploading the file
            uploaded_file: Django UploadedFile object
            chat_session_id: Optional associated chat session
            metadata: Additional metadata

        Returns:
            Created UserDocument instance

        Example:
            doc = DocumentProcessingService.create_document_record(
                user=request.user,
                uploaded_file=request.FILES['document'],
                chat_session_id=session.id
            )

            # Then trigger async processing
            process_document_task.delay(doc.id, user.id)
        """
        # Validate file type
        file_type = uploaded_file.content_type
        if file_type not in DocumentProcessingService.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported file type: {file_type}. "
                f"Supported: {', '.join(DocumentProcessingService.SUPPORTED_TYPES.values())}"
            )

        # Create document record
        doc = UserDocument.objects.create(
            user=user,
            chat_session_id=chat_session_id,
            file=uploaded_file,
            file_name=uploaded_file.name,
            file_size=uploaded_file.size,
            file_type=file_type,
            processing_status="pending",
            metadata=metadata or {},
        )

        return doc

    @staticmethod
    def load_document_text(file_path: str, file_type: str) -> str:
        """
        Extract text from document based on file type.

        Args:
            file_path: Path to the file
            file_type: MIME type of the file

        Returns:
            Extracted text content

        Raises:
            ValueError: If file type not supported or loading fails
        """
        try:
            # PDF
            if file_type == "application/pdf":
                loader = PyPDFLoader(file_path)
                pages = loader.load()
                return "\n\n".join([page.page_content for page in pages])

            # Plain text
            elif file_type == "text/plain":
                loader = TextLoader(file_path)
                docs = loader.load()
                return docs[0].page_content

            # Markdown
            elif file_type == "text/markdown":
                loader = UnstructuredMarkdownLoader(file_path)
                docs = loader.load()
                return docs[0].page_content

            # Word documents
            elif file_type in [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ]:
                loader = Docx2txtLoader(file_path)
                docs = loader.load()
                return docs[0].page_content

            else:
                raise ValueError(f"Unsupported file type: {file_type}")

        except Exception as e:
            raise ValueError(f"Failed to load document: {str(e)}")

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Split text into chunks for embedding.

        Args:
            text: Text to chunk
            chunk_size: Size of each chunk (characters)
            chunk_overlap: Overlap between chunks
            separators: Custom separators (optional)

        Returns:
            List of text chunks

        Example:
            chunks = DocumentProcessingService.chunk_text(
                text=document_text,
                chunk_size=1000,
                chunk_overlap=200
            )
        """
        # Default separators for better semantic chunking
        default_separators = [
            "\n\n",  # Paragraphs
            "\n",  # Lines
            ". ",  # Sentences
            ", ",  # Clauses
            " ",  # Words
            "",  # Characters
        ]

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or default_separators,
            length_function=len,
        )

        chunks = splitter.split_text(text)
        return chunks

    @staticmethod
    def process_document(
        document_id: UUID,
        user_id: UUID,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> UserDocument:
        """
        Complete document processing pipeline.

        This is typically called from a Celery task for async processing.

        Args:
            document_id: UserDocument ID
            user_id: User ID (for permission check)
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks

        Returns:
            Updated UserDocument instance

        Raises:
            Exception: If processing fails (stored in error_message)

        Example:
            # In Celery task
            @shared_task
            def process_document_task(document_id, user_id):
                return DocumentProcessingService.process_document(
                    document_id=document_id,
                    user_id=user_id
                )
        """
        # Get document and user
        doc = UserDocument.objects.get(id=document_id, user_id=user_id)
        user = CustomUser.objects.get(id=user_id)

        try:
            # Update status
            doc.processing_status = "processing"
            doc.save()

            # Get file path
            file_path = doc.file.path

            # Extract text
            text = DocumentProcessingService.load_document_text(
                file_path=file_path, file_type=doc.file_type
            )

            # Chunk text
            chunks = DocumentProcessingService.chunk_text(
                text=text, chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )

            # Store embeddings
            vector_ids = VectorStorageService.store_document_embeddings(
                document=doc, chunks=chunks, user=user
            )

            # Document is already marked as completed in store_document_embeddings

            return doc

        except Exception as e:
            # Mark as failed
            doc.processing_status = "failed"
            doc.error_message = str(e)
            doc.save()
            raise

    @staticmethod
    def reprocess_document(
        document_id: UUID,
        user_id: UUID,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> UserDocument:
        """
        Reprocess a document with different settings.

        Args:
            document_id: UserDocument ID
            user_id: User ID
            chunk_size: New chunk size (optional)
            chunk_overlap: New overlap (optional)

        Returns:
            Updated UserDocument instance

        Example:
            # Reprocess with larger chunks
            doc = DocumentProcessingService.reprocess_document(
                document_id=doc.id,
                user_id=user.id,
                chunk_size=2000
            )
        """
        doc = UserDocument.objects.get(id=document_id, user_id=user_id)
        user = CustomUser.objects.get(id=user_id)

        # Extract text
        file_path = doc.file.path
        text = DocumentProcessingService.load_document_text(
            file_path=file_path, file_type=doc.file_type
        )

        # Chunk with new settings
        chunks = DocumentProcessingService.chunk_text(
            text=text, chunk_size=chunk_size or 1000, chunk_overlap=chunk_overlap or 200
        )

        # Reindex
        VectorStorageService.reindex_document(
            document=doc, new_chunks=chunks, user=user
        )

        return doc

    @staticmethod
    def get_processing_status(document_id: UUID) -> Dict[str, Any]:
        """
        Get processing status for a document.

        Args:
            document_id: UserDocument ID

        Returns:
            Status information dict

        Example:
            status = DocumentProcessingService.get_processing_status(doc.id)
            if status['status'] == 'completed':
                print(f"Created {status['chunk_count']} chunks")
        """
        doc = UserDocument.objects.get(id=document_id)

        return {
            "document_id": str(doc.id),
            "file_name": doc.file_name,
            "status": doc.processing_status,
            "chunk_count": doc.chunk_count,
            "has_embeddings": doc.has_embeddings,
            "error_message": doc.error_message,
            "created_at": doc.created_at,
            "processed_at": doc.processed_at,
        }

    @staticmethod
    def delete_document(
        document_id: UUID, user_id: UUID, delete_file: bool = True
    ) -> None:
        """
        Delete document and its embeddings.

        Args:
            document_id: UserDocument ID
            user_id: User ID (for permission check)
            delete_file: Also delete the file from storage

        Example:
            DocumentProcessingService.delete_document(
                document_id=doc.id,
                user_id=user.id,
                delete_file=True
            )
        """
        doc = UserDocument.objects.get(id=document_id, user_id=user_id)

        # Delete embeddings first
        if doc.has_embeddings:
            VectorStorageService.delete_document_embeddings(doc)

        # Delete file if requested
        if delete_file and doc.file:
            file_path = doc.file.path
            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete database record
        doc.delete()

    @staticmethod
    def get_document_preview(document_id: UUID, max_length: int = 500) -> str:
        """
        Get preview of document content.

        Args:
            document_id: UserDocument ID
            max_length: Max characters to return

        Returns:
            Preview text

        Example:
            preview = DocumentProcessingService.get_document_preview(
                document_id=doc.id,
                max_length=200
            )
        """
        doc = UserDocument.objects.get(id=document_id)

        if not doc.file:
            return ""

        try:
            text = DocumentProcessingService.load_document_text(
                file_path=doc.file.path, file_type=doc.file_type
            )

            if len(text) > max_length:
                return text[:max_length] + "..."
            return text
        except:
            return "Preview not available"

    @staticmethod
    def validate_file(
        uploaded_file: UploadedFile, max_size_mb: int = 10
    ) -> Dict[str, Any]:
        """
        Validate uploaded file before processing.

        Args:
            uploaded_file: Django UploadedFile object
            max_size_mb: Maximum file size in MB

        Returns:
            Validation result dict

        Example:
            result = DocumentProcessingService.validate_file(
                uploaded_file=request.FILES['document'],
                max_size_mb=10
            )

            if not result['valid']:
                return Response(result, status=400)
        """
        errors = []

        # Check file type
        file_type = uploaded_file.content_type
        if file_type not in DocumentProcessingService.SUPPORTED_TYPES:
            errors.append(f"Unsupported file type: {file_type}")

        # Check file size
        max_bytes = max_size_mb * 1024 * 1024
        if uploaded_file.size > max_bytes:
            errors.append(
                f"File too large: {uploaded_file.size / (1024*1024):.2f}MB. "
                f"Maximum: {max_size_mb}MB"
            )

        # Check file name
        if not uploaded_file.name:
            errors.append("File name is required")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "file_name": uploaded_file.name,
            "file_type": file_type,
            "file_size_mb": uploaded_file.size / (1024 * 1024),
        }
