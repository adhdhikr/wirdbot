"""
ZIP Handler with Zip Bomb Detection
Safely handles ZIP file operations with security checks.
"""
import logging
import asyncio
import zipfile
import os
from pathlib import Path
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


class ZipSafetyError(Exception):
    """Raised when a ZIP file fails safety checks."""
    pass


# Safety thresholds
MAX_COMPRESSION_RATIO = 100  # Compressed:Uncompressed ratio
MAX_NESTING_DEPTH = 5  # Maximum nested ZIP levels
MAX_TOTAL_EXTRACTED_SIZE = 500 * 1024 * 1024  # 500MB max extraction
MAX_FILE_COUNT = 1000  # Maximum files in archive


async def check_zip_safety(file_path: str) -> Tuple[bool, str]:
    """
    Check if a ZIP file is safe to extract (no zip bomb).
    
    Checks performed:
    1. Compression ratio (compressed vs uncompressed size)
    2. Total uncompressed size
    3. Number of files
    4. Nested ZIP detection
    
    Args:
        file_path: Path to the ZIP file
    
    Returns:
        (is_safe, reason) tuple
    """
    path = Path(file_path)
    if not path.exists():
        return False, f"File not found: {file_path}"
    
    if not zipfile.is_zipfile(file_path):
        return False, "Not a valid ZIP file"
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _check_safety_sync, str(path))
        return result
    except Exception as e:
        logger.error(f"ZIP safety check failed: {e}")
        return False, f"Error checking ZIP: {e}"


def _check_safety_sync(file_path: str, depth: int = 0) -> Tuple[bool, str]:
    """Synchronous ZIP safety check."""
    if depth > MAX_NESTING_DEPTH:
        return False, f"Exceeded maximum nesting depth ({MAX_NESTING_DEPTH})"
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Get file info
            infos = zf.infolist()
            
            # Check file count
            if len(infos) > MAX_FILE_COUNT:
                return False, f"Too many files ({len(infos)} > {MAX_FILE_COUNT})"
            
            # Calculate sizes
            compressed_size = os.path.getsize(file_path)
            total_uncompressed = sum(info.file_size for info in infos)
            
            # Check total size
            if total_uncompressed > MAX_TOTAL_EXTRACTED_SIZE:
                return False, f"Total size too large ({_format_size(total_uncompressed)} > {_format_size(MAX_TOTAL_EXTRACTED_SIZE)})"
            
            # Check compression ratio
            if compressed_size > 0:
                ratio = total_uncompressed / compressed_size
                if ratio > MAX_COMPRESSION_RATIO:
                    return False, f"Suspicious compression ratio ({ratio:.1f}:1 > {MAX_COMPRESSION_RATIO}:1)"
            
            # Check for nested ZIPs
            nested_zips = [info for info in infos if info.filename.lower().endswith('.zip')]
            if nested_zips and depth < MAX_NESTING_DEPTH:
                # We don't recursively check nested ZIPs in this sync check
                # Just warn if there are many
                if len(nested_zips) > 10:
                    return False, f"Too many nested ZIP files ({len(nested_zips)})"
            
            return True, f"Safe: {len(infos)} files, {_format_size(total_uncompressed)} uncompressed"
            
    except zipfile.BadZipFile:
        return False, "Corrupted or invalid ZIP file"
    except Exception as e:
        return False, f"Error: {e}"


async def create_zip(
    files: List[str],
    output_path: str,
    base_dir: str = None
) -> str:
    """
    Create a ZIP archive from multiple files.
    
    Args:
        files: List of file paths to include
        output_path: Where to save the ZIP
        base_dir: Base directory for relative paths in archive
    
    Returns:
        Path to created ZIP or error message
    """
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _create_zip_sync, files, output_path, base_dir
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create ZIP: {e}")
        return f"Error creating ZIP: {e}"


def _create_zip_sync(
    files: List[str],
    output_path: str,
    base_dir: str = None
) -> str:
    """Synchronous ZIP creation."""
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            if not os.path.exists(file_path):
                continue
            
            # Determine archive name
            if base_dir:
                arcname = os.path.relpath(file_path, base_dir)
            else:
                arcname = os.path.basename(file_path)
            
            zf.write(file_path, arcname)
    
    return output_path


async def extract_zip(
    file_path: str,
    extract_to: str,
    check_safety: bool = True
) -> Tuple[bool, List[str]]:
    """
    Safely extract a ZIP file.
    
    Args:
        file_path: Path to the ZIP file
        extract_to: Directory to extract to
        check_safety: Whether to run safety checks first
    
    Returns:
        (success, list_of_extracted_files_or_error)
    """
    if check_safety:
        is_safe, reason = await check_zip_safety(file_path)
        if not is_safe:
            raise ZipSafetyError(f"ZIP failed safety check: {reason}")
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _extract_zip_sync, file_path, extract_to
        )
        return True, result
    except ZipSafetyError:
        raise
    except Exception as e:
        logger.error(f"Failed to extract ZIP: {e}")
        return False, [f"Error extracting ZIP: {e}"]


def _extract_zip_sync(file_path: str, extract_to: str) -> List[str]:
    """Synchronous safe ZIP extraction."""
    extracted_files = []
    
    # Ensure extraction directory exists
    os.makedirs(extract_to, exist_ok=True)
    
    with zipfile.ZipFile(file_path, 'r') as zf:
        for info in zf.infolist():
            # Skip directories
            if info.is_dir():
                continue
            
            # Security: prevent path traversal attacks
            member_path = os.path.normpath(info.filename)
            if member_path.startswith('..') or os.path.isabs(member_path):
                logger.warning(f"Skipping suspicious path: {info.filename}")
                continue
            
            # Extract file
            target_path = os.path.join(extract_to, member_path)
            
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # Extract with size limit check during extraction
            with zf.open(info.filename) as src:
                with open(target_path, 'wb') as dst:
                    bytes_written = 0
                    while True:
                        chunk = src.read(8192)
                        if not chunk:
                            break
                        bytes_written += len(chunk)
                        if bytes_written > MAX_TOTAL_EXTRACTED_SIZE:
                            raise ZipSafetyError("Extraction size limit exceeded during extraction")
                        dst.write(chunk)
            
            extracted_files.append(target_path)
    
    return extracted_files


async def list_zip_contents(file_path: str) -> List[dict]:
    """
    List contents of a ZIP file without extracting.
    
    Returns:
        List of dicts with filename, size, compressed_size, is_dir
    """
    if not zipfile.is_zipfile(file_path):
        return []
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _list_contents_sync, file_path)
        return result
    except Exception as e:
        logger.error(f"Failed to list ZIP contents: {e}")
        return []


def _list_contents_sync(file_path: str) -> List[dict]:
    """Synchronous ZIP content listing."""
    contents = []
    
    with zipfile.ZipFile(file_path, 'r') as zf:
        for info in zf.infolist():
            contents.append({
                'filename': info.filename,
                'size': info.file_size,
                'compressed_size': info.compress_size,
                'is_dir': info.is_dir(),
            })
    
    return contents


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
