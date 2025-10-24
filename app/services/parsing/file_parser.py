"""
Universal File Parser using Unstructured + LlamaIndex + EasyOCR
Extracts plain text from ANY file type (PDF, Word, Excel, Images, etc.)

Strategy:
1. PDFs: Fast mode first, then OCR for scanned PDFs (< 100 chars)
2. Images: EasyOCR (deep learning, no system dependencies)
3. Office files: Unstructured parsing (lightweight)
4. Lazy loading: Heavy ML models only loaded when needed
5. OCR: EasyOCR - 100% free, pure Python, no Tesseract needed
"""
import logging
import tempfile
import os
import base64
from typing import Tuple, Dict, Optional
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, Document
from llama_index.readers.file import UnstructuredReader
import magic

logger = logging.getLogger(__name__)


def extract_with_easyocr(file_path: str, file_type: str) -> Tuple[str, Dict]:
    """
    Extract text from images using EasyOCR (deep learning-based OCR).
    Fallback when Tesseract is not available. 100% free, no system dependencies.

    Args:
        file_path: Path to image file
        file_type: MIME type

    Returns:
        Tuple of (extracted_text, metadata)
    """
    import easyocr

    # Initialize EasyOCR reader (lazy load, cached after first use)
    # English only for now - add more languages as needed: ['en', 'es', 'fr']
    reader = easyocr.Reader(['en'], gpu=False)  # Use CPU (GPU optional if available)

    # Read text from image
    results = reader.readtext(file_path, detail=0)  # detail=0 returns only text, no bounding boxes

    # Join all detected text with newlines
    text = "\n".join(results)

    metadata = {
        "parser": "easyocr",
        "file_type": file_type,
        "file_name": Path(file_path).name,
        "file_size": os.path.getsize(file_path),
        "characters": len(text),
        "ocr_enabled": True,
        "ocr_method": "easyocr_deep_learning"
    }

    logger.info(f"   ✅ EasyOCR extracted {len(text)} characters")
    return text, metadata


def detect_file_type(file_path: str) -> str:
    """
    Detect MIME type of a file.

    Args:
        file_path: Path to file

    Returns:
        MIME type string (e.g., 'application/pdf')
    """
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

    # Try magic
    try:
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    except Exception as e:
        logger.warning(f"Failed to detect MIME type with magic: {e}, using extension fallback")

    # Use extension fallback
    ext = Path(file_path).suffix.lower()
    return ext_to_mime.get(ext, 'application/octet-stream')


def extract_text_from_file(
    file_path: str,
    file_type: Optional[str] = None
) -> Tuple[str, Dict]:
    """
    Extract text from any file type using hybrid strategy with OCR.

    Strategy:
    1. PDFs → Try fast mode first (text only), if < 100 chars → OCR (scanned PDF)
    2. Images → Tesseract OCR for text extraction
    3. Other files → standard Unstructured parsing

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

        # Special handling for PDFs (hybrid approach)
        if file_type == 'application/pdf':
            # Step 1: Try fast mode (text extraction only, no OCR)
            try:
                from unstructured.partition.pdf import partition_pdf
                elements = partition_pdf(
                    filename=file_path,
                    strategy="fast",
                    extract_images_in_pdf=False,
                    infer_table_structure=False
                )
                text = "\n\n".join([str(el) for el in elements])
                
                # Step 2: If we got barely any text, it's probably scanned - use EasyOCR!
                if len(text.strip()) < 100:
                    logger.warning(f"   ⚠️  Only {len(text)} chars extracted - PDF might be scanned, trying EasyOCR...")
                    try:
                        # Convert PDF to images and OCR each page
                        from pdf2image import convert_from_path
                        import tempfile

                        # Convert PDF pages to images
                        images = convert_from_path(file_path, dpi=200)
                        logger.info(f"   📄 Converted PDF to {len(images)} images for OCR")

                        # OCR each page
                        page_texts = []
                        for i, image in enumerate(images):
                            # Save image to temp file
                            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                                image.save(tmp.name, 'PNG')
                                tmp_path = tmp.name

                            # OCR the page image
                            try:
                                page_text, _ = extract_with_easyocr(tmp_path, 'image/png')
                                page_texts.append(page_text)
                                logger.info(f"   ✅ Page {i+1}: {len(page_text)} chars extracted")
                            finally:
                                os.unlink(tmp_path)

                        text = "\n\n".join(page_texts)
                        logger.info(f"   ✅ EasyOCR extracted {len(text)} chars from scanned PDF")
                    except Exception as ocr_err:
                        logger.warning(f"   ⚠️  PDF OCR failed: {ocr_err}, using fast extraction result")
                
                metadata = {
                    "parser": "unstructured_pdf",
                    "file_type": file_type,
                    "file_name": Path(file_path).name,
                    "file_size": os.path.getsize(file_path),
                    "characters": len(text),
                    "ocr_enabled": len(text.strip()) > 100  # OCR was used if we got more text
                }
                
            except Exception as pdf_error:
                logger.warning(f"PDF-specific parsing failed: {pdf_error}, falling back to generic parser")
                # Fall back to generic parser
                text, metadata = extract_with_generic_parser(file_path, file_type)
        
        # Special handling for images (OCR with EasyOCR)
        elif file_type in ['image/png', 'image/jpeg', 'image/jpg', 'image/tiff', 'image/bmp']:
            try:
                logger.info(f"   🔍 Running OCR on image (EasyOCR)...")
                text, metadata = extract_with_easyocr(file_path, file_type)
            except Exception as ocr_error:
                # ENTERPRISE FALLBACK: Even if OCR fails, still save the file
                # Parent email context will be added by ingest.py
                logger.error(f"   ❌ EasyOCR failed: {ocr_error}")
                logger.info(f"   💾 Saving file without OCR text (manual review may be needed)")

                text = ""  # Empty text, but file will still be stored
                metadata = {
                    "parser": "failed_ocr_fallback",
                    "file_type": file_type,
                    "file_name": Path(file_path).name,
                    "file_size": os.path.getsize(file_path),
                    "characters": 0,
                    "ocr_enabled": False,
                    "ocr_error": str(ocr_error),
                    "needs_manual_review": True,  # Flag for later reprocessing
                    "note": "OCR extraction failed - original file stored for manual review or reprocessing"
                }
        
        else:
            # Non-PDF, non-image files: use standard Unstructured
            text, metadata = extract_with_generic_parser(file_path, file_type)

        logger.info(f"✅ Extracted {len(text)} chars from {Path(file_path).name}")
        return text, metadata

    except Exception as e:
        error_msg = f"Failed to parse file {Path(file_path).name}: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def extract_with_generic_parser(file_path: str, file_type: str) -> Tuple[str, Dict]:
    """
    Extract text using generic Unstructured parser (for non-PDFs).
    """
    reader = SimpleDirectoryReader(
        input_files=[file_path],
        file_extractor={
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

    documents = reader.load_data()
    
    if not documents:
        raise ValueError("No content extracted from file")

    text = "\n\n".join([doc.text for doc in documents])
    
    metadata = {
        "parser": "unstructured",
        "file_type": file_type,
        "file_name": Path(file_path).name,
        "file_size": os.path.getsize(file_path),
        "num_documents": len(documents),
        "characters": len(text),
    }
    
    return text, metadata


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
