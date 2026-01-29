"""
File Processing Utilities Package
Provides PDF reading, Word document generation, and ZIP handling.
"""
from .pdf_reader import read_pdf, extract_pdf_pages, read_pdf_ordered, extract_pdf_images
from .docx_generator import create_word_doc
from .zip_handler import check_zip_safety, create_zip, extract_zip, ZipSafetyError

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
