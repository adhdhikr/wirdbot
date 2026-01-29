"""
PDF Reader Utility
Extracts text and images from PDF files using PyMuPDF (fitz).
Preserves visual order - text and images are extracted in the order they appear.
"""
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed. PDF reading will be unavailable.")


async def read_pdf(file_path: str, max_pages: int = None) -> str:
    """
    Extract all text from a PDF file (text only, no images).
    """
    if not PYMUPDF_AVAILABLE:
        return "Error: PyMuPDF is not installed."
    
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"
    
    try:
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
        return "PDF contains no extractable text. Use extract_pdf_images to get images for analysis."
    
    return "\n\n".join(text_parts)


async def read_pdf_ordered(
    file_path: str, 
    output_dir: str = None,
    max_pages: int = None,
    min_image_size: int = 100
) -> Dict[str, Any]:
    """
    Extract PDF content in visual order - text and images interleaved as they appear.
    
    Returns:
        Dict with 'content' list (ordered elements), 'text', 'images' list
    """
    if not PYMUPDF_AVAILABLE:
        return {"error": "PyMuPDF not installed"}
    
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _extract_ordered_sync, str(path), output_dir, max_pages, min_image_size
        )
        return result
    except Exception as e:
        logger.error(f"Failed to read PDF ordered: {e}")
        return {"error": str(e)}


def _extract_ordered_sync(
    file_path: str,
    output_dir: str,
    max_pages: int,
    min_image_size: int
) -> Dict[str, Any]:
    """Extract content in visual order using block positions."""
    doc = fitz.open(file_path)
    pdf_name = Path(file_path).stem
    
    all_content = []  # Ordered list of content blocks
    all_images = []   # Image info
    image_count = 0
    
    total_pages = len(doc)
    pages_to_read = min(total_pages, max_pages) if max_pages else total_pages
    
    for page_num in range(pages_to_read):
        page = doc[page_num]
        page_elements = []  # Elements with y-position for sorting
        
        # Get images for this page with their bounding boxes
        image_rects = {}  # xref -> rect
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                # Get all instances of this image on the page
                rects = page.get_image_rects(xref)
                if rects:
                    image_rects[xref] = rects[0]  # Use first occurrence
            except:
                pass
        
        # Get text blocks with positions
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        
        for block in blocks:
            bbox = block.get("bbox", (0, 0, 0, 0))
            y_pos = bbox[1]  # Top y coordinate
            
            if block.get("type") == 0:  # Text block
                text_lines = []
                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                    if line_text.strip():
                        text_lines.append(line_text)
                
                if text_lines:
                    page_elements.append({
                        "type": "text",
                        "content": "\n".join(text_lines),
                        "y_pos": y_pos
                    })
        
        # Add images in their positions
        if output_dir:
            for xref, rect in image_rects.items():
                try:
                    base_image = doc.extract_image(xref)
                    width = base_image["width"]
                    height = base_image["height"]
                    
                    # Skip tiny images
                    if width < min_image_size or height < min_image_size:
                        continue
                    
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    image_count += 1
                    filename = f"{pdf_name}_p{page_num + 1}_img{image_count}.{image_ext}"
                    save_path = Path(output_dir) / filename
                    
                    with open(save_path, "wb") as f:
                        f.write(image_bytes)
                    
                    img_info = {
                        "filename": filename,
                        "page": page_num + 1,
                        "width": width,
                        "height": height,
                        "path": str(save_path),
                        "size_bytes": len(image_bytes)
                    }
                    all_images.append(img_info)
                    
                    # Add to page elements at image position
                    page_elements.append({
                        "type": "image",
                        "content": f"[IMAGE: {filename} ({width}x{height})]",
                        "y_pos": rect.y0,  # Top of image
                        "image_info": img_info
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to extract image {xref}: {e}")
                    continue
        
        # Sort elements by y position (top to bottom)
        page_elements.sort(key=lambda x: x["y_pos"])
        
        # Build page content
        if page_elements:
            all_content.append({
                "type": "page_header",
                "content": f"\n--- Page {page_num + 1}/{total_pages} ---\n"
            })
            all_content.extend(page_elements)
    
    doc.close()
    
    # Build combined text with image placeholders in order
    combined_parts = []
    for item in all_content:
        combined_parts.append(item["content"])
    
    return {
        "content": all_content,
        "text": "\n".join(combined_parts),
        "images": all_images,
        "image_count": len(all_images),
        "page_count": pages_to_read
    }


async def extract_pdf_images(
    file_path: str, 
    output_dir: str,
    max_images: int = 20,
    min_size: int = 100
) -> List[Dict]:
    """Extract images from a PDF file and save them."""
    if not PYMUPDF_AVAILABLE:
        return [{"error": "PyMuPDF not installed"}]
    
    path = Path(file_path)
    if not path.exists():
        return [{"error": f"File not found: {file_path}"}]
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _extract_images_sync, str(path), str(output_dir), max_images, min_size
        )
        return result
    except Exception as e:
        logger.error(f"Failed to extract PDF images: {e}")
        return [{"error": str(e)}]


def _extract_images_sync(
    file_path: str, 
    output_dir: str, 
    max_images: int,
    min_size: int
) -> List[Dict]:
    """Synchronous image extraction from PDF."""
    doc = fitz.open(file_path)
    extracted = []
    image_count = 0
    pdf_name = Path(file_path).stem
    
    for page_num in range(len(doc)):
        if image_count >= max_images:
            break
            
        page = doc[page_num]
        image_list = page.get_images(full=True)
        
        for img in image_list:
            if image_count >= max_images:
                break
                
            xref = img[0]
            
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                width = base_image["width"]
                height = base_image["height"]
                
                if width < min_size or height < min_size:
                    continue
                
                image_count += 1
                filename = f"{pdf_name}_p{page_num + 1}_img{image_count}.{image_ext}"
                save_path = Path(output_dir) / filename
                
                with open(save_path, "wb") as f:
                    f.write(image_bytes)
                
                extracted.append({
                    "filename": filename,
                    "page": page_num + 1,
                    "width": width,
                    "height": height,
                    "path": str(save_path),
                    "size_bytes": len(image_bytes)
                })
                
            except Exception as e:
                logger.warning(f"Failed to extract image {xref}: {e}")
                continue
    
    doc.close()
    return extracted



async def extract_pdf_pages(file_path: str, start_page: int = 1, end_page: int = None) -> str:
    """
    Extract text from specific pages of a PDF.
    """
    if not PYMUPDF_AVAILABLE:
        return "Error: PyMuPDF is not installed."
    
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
        logger.error(f"Failed to extract PDF pages: {e}")
        return f"Error extracting PDF pages: {e}"


def _extract_pages_sync(file_path: str, start_page: int, end_page: int = None) -> str:
    """Synchronous page range extraction."""
    doc = fitz.open(file_path)
    text_parts = []
    
    total_pages = len(doc)
    start_idx = max(0, start_page - 1)
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
    """Get metadata about a PDF file."""
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
