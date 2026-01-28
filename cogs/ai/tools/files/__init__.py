"""
File Processing Utilities Package
Provides PDF reading, Word document generation, and ZIP handling.
"""
from .pdf_reader import read_pdf, extract_pdf_pages
from .docx_generator import create_word_doc, create_word_doc_with_latex
from .zip_handler import check_zip_safety, create_zip, extract_zip, ZipSafetyError

__all__ = [
    'read_pdf',
    'extract_pdf_pages',
    'create_word_doc',
    'create_word_doc_with_latex',
    'check_zip_safety',
    'create_zip',
    'extract_zip',
    'ZipSafetyError',
]
