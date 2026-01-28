"""
Word Document Generator
Creates .docx files with support for LaTeX equation rendering.
"""
import logging
import asyncio
import re
import os
from pathlib import Path
from typing import Optional, List
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed. Word doc creation will be unavailable.")

try:
    from latex2mathml.converter import convert as latex_to_mathml
    LATEX_AVAILABLE = True
except ImportError:
    LATEX_AVAILABLE = False
    logger.warning("latex2mathml not installed. LaTeX equations will be plain text.")


# Regex patterns for LaTeX
DISPLAY_MATH_PATTERN = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
INLINE_MATH_PATTERN = re.compile(r'\$([^\$\n]+?)\$')


async def create_word_doc(
    content: str,
    output_path: str,
    title: str = None,
    convert_latex: bool = True
) -> str:
    """
    Create a Word document from text content.
    
    Args:
        content: The text content to put in the document
        output_path: Where to save the .docx file
        title: Optional document title
        convert_latex: Whether to convert $...$ and $$...$$ to equations
    
    Returns:
        Path to created file or error message
    """
    if not DOCX_AVAILABLE:
        return "Error: python-docx is not installed. Cannot create Word documents."
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _create_doc_sync, content, output_path, title, convert_latex
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create Word doc: {e}")
        return f"Error creating Word document: {e}"


def _create_doc_sync(
    content: str,
    output_path: str,
    title: str = None,
    convert_latex: bool = True
) -> str:
    """Synchronous document creation."""
    doc = Document()
    
    # Add title if provided
    if title:
        title_para = doc.add_heading(title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Process content
    if convert_latex and LATEX_AVAILABLE:
        _add_content_with_latex(doc, content)
    else:
        # Simple paragraph-based addition
        for para_text in content.split('\n\n'):
            if para_text.strip():
                doc.add_paragraph(para_text.strip())
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save document
    doc.save(output_path)
    return output_path


def _add_content_with_latex(doc: Document, content: str):
    """
    Add content to document, converting LaTeX equations.
    
    Note: python-docx doesn't have native equation support, so we use
    a workaround: LaTeX is converted to a readable format and styled differently.
    For true OMML equations, more complex XML manipulation would be needed.
    """
    # Split by paragraphs
    paragraphs = content.split('\n\n')
    
    for para_text in paragraphs:
        if not para_text.strip():
            continue
        
        # Check for display math ($$...$$)
        if '$$' in para_text:
            parts = DISPLAY_MATH_PATTERN.split(para_text)
            para = doc.add_paragraph()
            
            is_math = False
            for i, part in enumerate(parts):
                if i % 2 == 1:  # This is a math part
                    # Add equation as formatted text
                    run = para.add_run(f'\n[Equation: {part.strip()}]\n')
                    run.italic = True
                    run.font.size = Pt(11)
                else:
                    if part.strip():
                        para.add_run(part)
        
        # Check for inline math ($...$)
        elif '$' in para_text:
            para = doc.add_paragraph()
            parts = INLINE_MATH_PATTERN.split(para_text)
            
            for i, part in enumerate(parts):
                if i % 2 == 1:  # This is a math part
                    run = para.add_run(part)
                    run.italic = True
                    run.font.name = 'Cambria Math'
                else:
                    if part:
                        para.add_run(part)
        
        else:
            # Regular paragraph
            doc.add_paragraph(para_text.strip())


async def create_word_doc_with_latex(
    sections: List[dict],
    output_path: str,
    title: str = None
) -> str:
    """
    Create a structured Word document with sections.
    
    Args:
        sections: List of dicts with 'heading', 'level', 'content' keys
        output_path: Where to save the .docx file
        title: Optional document title
    
    Returns:
        Path to created file or error message
    
    Example:
        sections = [
            {'heading': 'Problem 1', 'level': 1, 'content': 'Solve $x^2 + 2x + 1 = 0$'},
            {'heading': 'Solution', 'level': 2, 'content': 'Using quadratic formula...'},
        ]
    """
    if not DOCX_AVAILABLE:
        return "Error: python-docx is not installed."
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _create_structured_doc_sync, sections, output_path, title
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create structured Word doc: {e}")
        return f"Error creating Word document: {e}"


def _create_structured_doc_sync(
    sections: List[dict],
    output_path: str,
    title: str = None
) -> str:
    """Synchronous structured document creation."""
    doc = Document()
    
    # Add title
    if title:
        title_para = doc.add_heading(title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Add sections
    for section in sections:
        heading = section.get('heading')
        level = section.get('level', 1)
        content = section.get('content', '')
        
        if heading:
            doc.add_heading(heading, level=min(level, 9))
        
        if content:
            if LATEX_AVAILABLE:
                _add_content_with_latex(doc, content)
            else:
                doc.add_paragraph(content)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save
    doc.save(output_path)
    return output_path


async def create_word_doc_bytes(
    content: str,
    title: str = None,
    convert_latex: bool = True
) -> Optional[BytesIO]:
    """
    Create a Word document and return as bytes (for Discord upload).
    
    Returns:
        BytesIO object containing the document, or None on error
    """
    if not DOCX_AVAILABLE:
        return None
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _create_doc_bytes_sync, content, title, convert_latex
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create Word doc bytes: {e}")
        return None


def _create_doc_bytes_sync(
    content: str,
    title: str = None,
    convert_latex: bool = True
) -> BytesIO:
    """Create document and return as BytesIO."""
    doc = Document()
    
    if title:
        title_para = doc.add_heading(title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    if convert_latex and LATEX_AVAILABLE:
        _add_content_with_latex(doc, content)
    else:
        for para_text in content.split('\n\n'):
            if para_text.strip():
                doc.add_paragraph(para_text.strip())
    
    # Save to BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
