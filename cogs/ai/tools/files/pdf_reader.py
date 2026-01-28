"""
PDF Reader Utility
Extracts text from PDF files using PyMuPDF (fitz).
"""
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed. PDF reading will be unavailable. Install with: pip install PyMuPDF")


async def read_pdf(file_path: str, max_pages: int = None) -> str:
    """
    Extract all text from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        max_pages: Maximum number of pages to extract (None = all)
    
    Returns:
        Extracted text with page markers
    """
    if not PYMUPDF_AVAILABLE:
        return "Error: PyMuPDF is not installed. Cannot read PDF files."
    
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"
    
    if not path.suffix.lower() == '.pdf':
        return f"Error: Not a PDF file: {file_path}"
    
    try:
        # Run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _extract_text_sync, str(path), max_pages)
        return result
    except Exception as e:
        logger.error(f"Failed to read PDF {file_path}: {e}")
        return f"Error reading PDF: {e}"


def _extract_text_sync(file_path: str, max_pages: int = None) -> str:
    """Synchronous PDF text extraction."""
    doc = fitz.open(file_path)
    text_parts = []
    
    total_pages = len(doc)
    pages_to_read = min(total_pages, max_pages) if max_pages else total_pages
    
    for page_num in range(pages_to_read):
        page = doc[page_num]
        text = page.get_text()
        
        if text.strip():
            text_parts.append(f"--- Page {page_num + 1}/{total_pages} ---\n{text}")
    
    doc.close()
    
    if not text_parts:
        return "PDF contains no extractable text (may be scanned/image-based)."
    
    return "\n\n".join(text_parts)


async def extract_pdf_pages(file_path: str, start_page: int = 1, end_page: int = None) -> str:
    """
    Extract text from specific pages of a PDF.
    
    Args:
        file_path: Path to the PDF file
        start_page: Starting page number (1-indexed)
        end_page: Ending page number (inclusive, None = to end)
    
    Returns:
        Extracted text from specified pages
    """
    if not PYMUPDF_AVAILABLE:
        return "Error: PyMuPDF is not installed. Cannot read PDF files."
    
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _extract_pages_sync, str(path), start_page, end_page
        )
        return result
    except Exception as e:
        logger.error(f"Failed to extract PDF pages {file_path}: {e}")
        return f"Error extracting PDF pages: {e}"


def _extract_pages_sync(file_path: str, start_page: int, end_page: int = None) -> str:
    """Synchronous page range extraction."""
    doc = fitz.open(file_path)
    text_parts = []
    
    total_pages = len(doc)
    start_idx = max(0, start_page - 1)  # Convert to 0-indexed
    end_idx = min(total_pages, end_page) if end_page else total_pages
    
    for page_num in range(start_idx, end_idx):
        page = doc[page_num]
        text = page.get_text()
        
        if text.strip():
            text_parts.append(f"--- Page {page_num + 1}/{total_pages} ---\n{text}")
    
    doc.close()
    
    if not text_parts:
        return "No text found in specified pages."
    
    return "\n\n".join(text_parts)


async def get_pdf_info(file_path: str) -> Dict:
    """
    Get metadata about a PDF file.
    
    Returns:
        Dict with page_count, metadata, file_size
    """
    if not PYMUPDF_AVAILABLE:
        return {"error": "PyMuPDF not installed"}
    
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _get_info_sync, str(path))
        result['file_size'] = path.stat().st_size
        return result
    except Exception as e:
        return {"error": str(e)}


def _get_info_sync(file_path: str) -> Dict:
    """Synchronous PDF info extraction."""
    doc = fitz.open(file_path)
    info = {
        'page_count': len(doc),
        'metadata': doc.metadata,
        'is_encrypted': doc.is_encrypted,
    }
    doc.close()
    return info
