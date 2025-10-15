"""
Universal File Parser using Unstructured + LlamaIndex
Extracts plain text from ANY file type (PDF, Word, Excel, images, etc.)
100% LOCAL - no API calls
"""
import logging
import tempfile
import os
from typing import Tuple, Dict, Optional
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, Document
from llama_index.readers.file import UnstructuredReader
import magic

logger = logging.getLogger(__name__)


def detect_file_type(file_path: str) -> str:
    """
    Detect MIME type of a file.

    Args:
        file_path: Path to file

    Returns:
        MIME type string (e.g., 'application/pdf')
    """
    try:
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    except Exception as e:
        logger.warning(f"Failed to detect MIME type: {e}, using extension fallback")
        # Fallback: guess from extension
        ext_to_mime = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.md': 'text/markdown',
        }
        ext = Path(file_path).suffix.lower()
        return ext_to_mime.get(ext, 'application/octet-stream')


def extract_text_from_file(
    file_path: str,
    file_type: Optional[str] = None
) -> Tuple[str, Dict]:
    """
    Extract text from any file type using LlamaIndex + Unstructured.

    Supports:
    - PDFs (application/pdf)
    - Word docs (.docx, .doc)
    - PowerPoint (.pptx)
    - Excel (.xlsx)
    - Images (with OCR)
    - Text files (.txt, .md, .html)
    - And 20+ more file types

    Args:
        file_path: Path to file
        file_type: Optional MIME type (auto-detected if not provided)

    Returns:
        (extracted_text, metadata_dict)

    Raises:
        ValueError: If file parsing fails
    """
    try:
        # Detect file type if not provided
        if not file_type:
            file_type = detect_file_type(file_path)

        logger.info(f"📄 Parsing file: {Path(file_path).name} ({file_type})")

        # Use LlamaIndex SimpleDirectoryReader with UnstructuredReader backend
        # UnstructuredReader runs 100% locally (no API calls)
        reader = SimpleDirectoryReader(
            input_files=[file_path],
            file_extractor={
                ".pdf": UnstructuredReader(),
                ".docx": UnstructuredReader(),
                ".doc": UnstructuredReader(),
                ".pptx": UnstructuredReader(),
                ".ppt": UnstructuredReader(),
                ".xlsx": UnstructuredReader(),
                ".xls": UnstructuredReader(),
                ".txt": UnstructuredReader(),
                ".md": UnstructuredReader(),
                ".html": UnstructuredReader(),
                ".htm": UnstructuredReader(),
                ".csv": UnstructuredReader(),
                ".json": UnstructuredReader(),
                ".xml": UnstructuredReader(),
                ".eml": UnstructuredReader(),
                ".msg": UnstructuredReader(),
                ".rtf": UnstructuredReader(),
                ".odt": UnstructuredReader(),
            }
        )

        # Load documents (returns list of LlamaIndex Document objects)
        documents = reader.load_data()

        if not documents:
            raise ValueError("No content extracted from file")

        # Combine all document text (in case file was split into multiple docs)
        text = "\n\n".join([doc.text for doc in documents])

        # Build metadata
        metadata = {
            "parser": "unstructured",
            "file_type": file_type,
            "file_name": Path(file_path).name,
            "file_size": os.path.getsize(file_path),
            "num_documents": len(documents),
            "characters": len(text),
        }

        logger.info(f"✅ Extracted {len(text)} chars from {Path(file_path).name}")

        return text, metadata

    except Exception as e:
        error_msg = f"Failed to parse file {Path(file_path).name}: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def extract_text_from_bytes(
    file_bytes: bytes,
    filename: str,
    file_type: Optional[str] = None
) -> Tuple[str, Dict]:
    """
    Extract text from file bytes (for uploads or API responses).

    Args:
        file_bytes: File content as bytes
        filename: Original filename (used for extension detection)
        file_type: Optional MIME type

    Returns:
        (extracted_text, metadata_dict)

    Raises:
        ValueError: If file parsing fails
    """
    # Save bytes to temporary file
    ext = Path(filename).suffix or '.bin'
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        # Extract text from temp file
        text, metadata = extract_text_from_file(tmp_path, file_type)

        # Add original filename to metadata
        metadata['original_filename'] = filename
        metadata['file_size'] = len(file_bytes)

        return text, metadata

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")


def is_parseable_file(file_type: str) -> bool:
    """
    Check if a file type is parseable by Unstructured.

    Args:
        file_type: MIME type string

    Returns:
        True if file can be parsed, False otherwise
    """
    parseable_types = [
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/rtf",
        "application/vnd.oasis.opendocument.text",

        # Text
        "text/plain",
        "text/html",
        "text/markdown",
        "text/csv",
        "text/xml",
        "application/json",

        # Email
        "message/rfc822",
        "application/vnd.ms-outlook",

        # Images (with OCR)
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
    ]

    return file_type in parseable_types


def get_extension_from_mime(mime_type: str) -> str:
    """
    Get file extension from MIME type.

    Args:
        mime_type: MIME type string

    Returns:
        File extension (e.g., '.pdf')
    """
    mime_to_ext = {
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "text/plain": ".txt",
        "text/html": ".html",
        "text/markdown": ".md",
        "text/csv": ".csv",
        "application/json": ".json",
        "text/xml": ".xml",
        "message/rfc822": ".eml",
        "application/vnd.ms-outlook": ".msg",
        "application/rtf": ".rtf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/tiff": ".tiff",
    }
    return mime_to_ext.get(mime_type, ".bin")
