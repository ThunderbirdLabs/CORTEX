"""
File parsing services.
Handles extraction of text from any file type (PDFs, Word, images, etc.)
"""
from app.services.parsing.file_parser import extract_text_from_file, extract_text_from_bytes

__all__ = ["extract_text_from_file", "extract_text_from_bytes"]
