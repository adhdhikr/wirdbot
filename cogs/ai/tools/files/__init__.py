"""
File Processing Utilities Package
Provides PDF reading, Word document generation, and ZIP handling.
"""
from .docx_generator import create_word_doc
from .pdf_reader import (
    extract_pdf_images,
    extract_pdf_pages,
    read_pdf,
    read_pdf_ordered,
)
from .zip_handler import ZipSafetyError, check_zip_safety, create_zip, extract_zip

__all__ = [
    'read_pdf',
    'extract_pdf_pages',
    'read_pdf_ordered',
    'extract_pdf_images',
    'create_word_doc',
    'check_zip_safety',
    'create_zip',
    'extract_zip',
    'ZipSafetyError',
]
