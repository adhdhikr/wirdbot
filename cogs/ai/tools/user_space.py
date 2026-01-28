"""
User Space Tools
AI-callable tools for managing user file storage.
"""
import logging
import os
import aiohttp
import aiofiles
import asyncio
import mimetypes
from pathlib import Path
from typing import Optional
from io import BytesIO

from database import Database
from .files import read_pdf, create_word_doc, check_zip_safety, create_zip, extract_zip, ZipSafetyError
from .files.docx_generator import create_word_doc_bytes

logger = logging.getLogger(__name__)

# Base directory for user files
USER_FILES_BASE = Path("data/user_files")


def _get_user_dir(user_id: int) -> Path:
    """Get the storage directory for a user."""
    user_dir = USER_FILES_BASE / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    # Remove path separators
    filename = os.path.basename(filename)
    # Remove potentially dangerous characters
    dangerous_chars = ['..', '/', '\\', '\x00']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    return filename or 'unnamed_file'


async def _get_file_repo():
    """Get the file storage repository."""
    from db.repositories.file_storage import FileStorageRepository
    db = Database()
    return FileStorageRepository(db.connection)


# ============================================================================
# UPLOAD & SAVE TOOLS
# ============================================================================

async def save_to_space(
    content: str,
    filename: str,
    file_type: str = None,
    title: str = None,
    **kwargs
) -> str:
    """
    Save generated content as a file in the user's personal space.
    
    Use this to save AI-generated content like solutions, summaries, code, or documents.
    Supports any text-based file type.
    
    Args:
        content: The text content to save
        filename: Name for the file (include extension like "code.py" or "notes.txt")
        file_type: Optional override for file type ("txt", "docx", "json", "csv", "py", "java", etc.)
        title: Optional title for Word documents
    
    Returns:
        Success message with file info, or error message
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    # Sanitize filename
    filename = _sanitize_filename(filename)
    
    # Determine file extension
    if '.' in filename:
        # Already has extension - use it
        base_name, ext = os.path.splitext(filename)
        actual_type = ext[1:] if ext else 'txt'  # Remove the dot
    else:
        # No extension - use file_type or default to txt
        actual_type = file_type or 'txt'
        filename = f"{filename}.{actual_type}"
    
    # If file_type is explicitly specified and different, use it
    if file_type and not filename.endswith(f'.{file_type}'):
        base_name = os.path.splitext(filename)[0]
        filename = f"{base_name}.{file_type}"
        actual_type = file_type
    
    user_dir = _get_user_dir(user_id)
    file_path = user_dir / filename
    
    try:
        repo = await _get_file_repo()
        
        # Check if file already exists
        existing = await repo.get_file(user_id, filename)
        overwriting = existing is not None
        if existing:
            await repo.delete_file(user_id, filename)
            if Path(existing['file_path']).exists():
                os.remove(existing['file_path'])
        
        # Create the file based on type
        if actual_type == "docx":
            result_path = await create_word_doc(content, str(file_path), title=title)
            if result_path.startswith("Error"):
                return result_path
        else:
            # Any text-based file (txt, json, csv, py, java, js, html, etc.)
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Check storage limits
        can_upload, reason = await repo.can_upload(user_id, file_size)
        if not can_upload:
            os.remove(file_path)
            return f"❌ {reason}"
        
        # Add to database
        mime_type = mimetypes.guess_type(filename)[0] or 'text/plain'
        await repo.add_file(
            user_id=user_id,
            filename=filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=mime_type
        )
        
        # Get updated storage info
        usage = await repo.get_storage_usage(user_id)
        
        # Build detailed response
        action = "Overwrote" if overwriting else "Saved"
        content_preview = content[:100].replace('\n', ' ').strip()
        if len(content) > 100:
            content_preview += "..."
        
        response = f"✅ **{action}:** `{filename}`\n"
        response += f"📄 **Type:** {actual_type.upper()} | **Size:** {_format_size(file_size)}\n"
        response += f"� **Preview:** `{content_preview}`\n"
        response += f"📁 **Storage:** {usage['usage_percent']:.1f}% used ({_format_size(usage['total_bytes_used'])} / {_format_size(usage['max_storage'])})"
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        return f"❌ Error saving file: {e}"


async def upload_attachment_to_space(
    attachment_url: str,
    filename: str = None,
    **kwargs
) -> str:
    """
    Download and save a Discord attachment to the user's personal space.
    
    Use this when a user sends a file and wants to store it for later use.
    Handles PDFs, images, documents, and ZIP files (with safety checks).
    
    Args:
        attachment_url: The URL of the Discord attachment to download
        filename: Optional custom filename; uses original if not provided
    
    Returns:
        Success message with file info, or error message
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        
        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment_url) as resp:
                if resp.status != 200:
                    return f"❌ Failed to download file: HTTP {resp.status}"
                
                # Get filename from URL if not provided
                if not filename:
                    filename = attachment_url.split('/')[-1].split('?')[0]
                
                filename = _sanitize_filename(filename)
                file_data = await resp.read()
        
        file_size = len(file_data)
        
        # Check storage limits
        can_upload, reason = await repo.can_upload(user_id, file_size)
        if not can_upload:
            return f"❌ {reason}"
        
        # Check if it's a ZIP and validate safety
        if filename.lower().endswith('.zip'):
            # Save temporarily to check
            temp_path = _get_user_dir(user_id) / f".temp_{filename}"
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(file_data)
            
            is_safe, safety_msg = await check_zip_safety(str(temp_path))
            if not is_safe:
                os.remove(temp_path)
                return f"❌ **ZIP Safety Check Failed:** {safety_msg}"
            
            # Rename temp to final
            file_path = _get_user_dir(user_id) / filename
            os.rename(temp_path, file_path)
        else:
            # Save regular file
            file_path = _get_user_dir(user_id) / filename
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
        
        # Check for duplicate filename
        existing = await repo.get_file(user_id, filename)
        if existing:
            await repo.delete_file(user_id, filename)
        
        # Add to database
        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        await repo.add_file(
            user_id=user_id,
            filename=filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=mime_type
        )
        
        usage = await repo.get_storage_usage(user_id)
        
        return f"✅ **Uploaded:** `{filename}` ({_format_size(file_size)})\n📁 Space used: {usage['usage_percent']:.1f}%"
        
    except Exception as e:
        logger.error(f"Failed to upload attachment: {e}")
        return f"❌ Error uploading file: {e}"


async def save_message_attachments(**kwargs) -> str:
    """
    Save all attachments from the user's current message to their personal space.
    
    Use this when a user sends files and wants to store them. This automatically
    detects and saves all files attached to the message.
    
    Returns:
        Success message listing saved files, or error if no attachments found
    """
    user_id = kwargs.get('user_id')
    message = kwargs.get('message')
    
    if not user_id:
        return "Error: Could not determine user ID"
    
    if not message:
        return "Error: Could not access message context"
    
    attachments = message.attachments
    if not attachments:
        return "❌ No attachments found in the message. Send a file with your request."
    
    results = []
    for att in attachments:
        result = await upload_attachment_to_space(
            attachment_url=att.url,
            filename=att.filename,
            user_id=user_id
        )
        results.append(f"• **{att.filename}**: {result}")
    
    return f"📁 **Saving {len(attachments)} file(s):**\n" + "\n".join(results)


# ============================================================================
# READ & PROCESS TOOLS
# ============================================================================

async def read_from_space(filename: str, **kwargs) -> str:
    """
    Read the contents of a file from the user's personal space.
    
    For PDF files, extracts the text content.
    For text files, returns the raw content.
    For other files, returns file info.
    
    Args:
        filename: Name of the file to read
    
    Returns:
        File contents or error message
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        
        file_info = await repo.get_file(user_id, filename)
        if not file_info:
            return f"❌ File not found: `{filename}`\nUse `list_space()` to see your files."
        
        file_path = Path(file_info['file_path'])
        if not file_path.exists():
            return f"❌ File missing from storage: `{filename}`"
        
        # Update last_accessed to keep file from being cleaned up
        await repo.update_last_accessed(user_id, filename)
        
        # Handle by file type
        ext = file_path.suffix.lower()
        
        if ext == '.pdf':
            content = await read_pdf(str(file_path))
            return f"📄 **Contents of `{filename}`:**\n\n{content}"
        
        elif ext in ['.txt', '.md', '.json', '.csv', '.py', '.js', '.html', '.css']:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Truncate if too long
            if len(content) > 4000:
                content = content[:4000] + "\n\n... (truncated)"
            
            return f"📄 **Contents of `{filename}`:**\n```\n{content}\n```"
        
        elif ext == '.zip':
            from .files.zip_handler import list_zip_contents
            contents = await list_zip_contents(str(file_path))
            file_list = "\n".join([f"  - {c['filename']} ({_format_size(c['size'])})" for c in contents[:20]])
            if len(contents) > 20:
                file_list += f"\n  ... and {len(contents) - 20} more files"
            return f"📦 **ZIP Contents of `{filename}`:**\n{file_list}"
        
        else:
            return f"📁 **File:** `{filename}`\nType: {file_info.get('mime_type', 'unknown')}\nSize: {_format_size(file_info['file_size'])}\n\n(Cannot display binary file contents)"
            
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return f"❌ Error reading file: {e}"


# ============================================================================
# SPACE MANAGEMENT TOOLS
# ============================================================================

async def list_space(**kwargs) -> str:
    """
    List all files in the user's personal storage space.
    
    Shows filename, size, and upload date for each file.
    
    Returns:
        Formatted list of files or message if space is empty
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        
        files = await repo.list_files(user_id)
        
        if not files:
            return "📂 **Your Space is Empty**\nUpload files by sending them to me, or use `save_to_space()` to save generated content."
        
        # Update last_accessed on first file to mark user as active
        # This prevents cleanup of their space while they're using it
        if files:
            await repo.update_last_accessed(user_id, files[0]['filename'])
        
        usage = await repo.get_storage_usage(user_id)
        
        file_list = []
        for f in files:
            size_str = _format_size(f['file_size'])
            file_list.append(f"• `{f['filename']}` - {size_str}")
        
        header = f"📂 **Your Files** ({len(files)} files, {usage['usage_percent']:.1f}% used)\n"
        header += f"Storage: {_format_size(usage['total_bytes_used'])} / {_format_size(usage['max_storage'])}\n\n"
        
        return header + "\n".join(file_list)
        
    except Exception as e:
        logger.error(f"Failed to list space: {e}")
        return f"❌ Error listing files: {e}"


async def get_space_info(**kwargs) -> str:
    """
    Get detailed storage usage information for the user's space.
    
    Returns:
        Storage statistics including used space, remaining space, and limits
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        usage = await repo.get_storage_usage(user_id)
        
        return f"""📊 **Storage Info**
        
**Used:** {_format_size(usage['total_bytes_used'])} / {_format_size(usage['max_storage'])} ({usage['usage_percent']:.1f}%)
**Remaining:** {_format_size(usage['bytes_remaining'])}
**File Count:** {usage['file_count']}
**Max File Size:** {_format_size(usage['max_file_size'])}"""
        
    except Exception as e:
        logger.error(f"Failed to get space info: {e}")
        return f"❌ Error getting space info: {e}"


async def delete_from_space(filename: str, **kwargs) -> str:
    """
    Delete a file from the user's personal space.
    
    This permanently removes the file and frees up storage space.
    
    Args:
        filename: Name of the file to delete
    
    Returns:
        Success or error message
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        
        file_info = await repo.get_file(user_id, filename)
        if not file_info:
            return f"❌ File not found: `{filename}`"
        
        file_size = file_info['file_size']
        file_path = Path(file_info['file_path'])
        
        # Delete from database
        success = await repo.delete_file(user_id, filename)
        if not success:
            return f"❌ Failed to delete file record"
        
        # Delete actual file
        if file_path.exists():
            os.remove(file_path)
        
        return f"🗑️ **Deleted:** `{filename}` ({_format_size(file_size)} freed)"
        
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        return f"❌ Error deleting file: {e}"


# ============================================================================
# ZIP OPERATIONS
# ============================================================================

async def zip_files(filenames: str, output_name: str, **kwargs) -> str:
    """
    Create a ZIP archive from multiple files in the user's space.
    
    Args:
        filenames: Comma-separated list of filenames to include (e.g. "file1.pdf, file2.txt")
        output_name: Name for the output ZIP file (without .zip extension)
    
    Returns:
        Success message with ZIP file info, or error message
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        user_dir = _get_user_dir(user_id)
        
        # Parse comma-separated filenames
        filename_list = [f.strip() for f in filenames.split(',') if f.strip()]
        if not filename_list:
            return "❌ No filenames provided. Use comma-separated list like: file1.pdf, file2.txt"
        
        # Validate input files
        files_to_zip = []
        for filename in filename_list:
            file_info = await repo.get_file(user_id, filename)
            if not file_info:
                return f"❌ File not found: `{filename}`"
            
            file_path = Path(file_info['file_path'])
            if not file_path.exists():
                return f"❌ File missing: `{filename}`"
            
            files_to_zip.append(str(file_path))
        
        # Create output path
        output_name = _sanitize_filename(output_name)
        if not output_name.endswith('.zip'):
            output_name = f"{output_name}.zip"
        
        output_path = user_dir / output_name
        
        # Create ZIP
        result = await create_zip(files_to_zip, str(output_path), str(user_dir))
        if result.startswith("Error"):
            return f"❌ {result}"
        
        # Get file size
        zip_size = output_path.stat().st_size
        
        # Check storage limits
        can_upload, reason = await repo.can_upload(user_id, zip_size)
        if not can_upload:
            os.remove(output_path)
            return f"❌ {reason}"
        
        # Add to database
        await repo.add_file(
            user_id=user_id,
            filename=output_name,
            original_filename=output_name,
            file_path=str(output_path),
            file_size=zip_size,
            mime_type='application/zip'
        )
        
        return f"✅ **Created:** `{output_name}` ({_format_size(zip_size)})\nContains {len(files_to_zip)} files."
        
    except Exception as e:
        logger.error(f"Failed to create ZIP: {e}")
        return f"❌ Error creating ZIP: {e}"


async def unzip_file(filename: str, **kwargs) -> str:
    """
    Extract a ZIP file's contents to the user's space.
    
    Includes zip bomb detection for safety. Extracted files are added
    to the user's space individually.
    
    Args:
        filename: Name of the ZIP file to extract
    
    Returns:
        Success message listing extracted files, or error message
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        
        file_info = await repo.get_file(user_id, filename)
        if not file_info:
            return f"❌ File not found: `{filename}`"
        
        file_path = Path(file_info['file_path'])
        if not file_path.exists():
            return f"❌ File missing from storage"
        
        if not filename.lower().endswith('.zip'):
            return f"❌ Not a ZIP file: `{filename}`"
        
        user_dir = _get_user_dir(user_id)
        extract_dir = user_dir / f"_extracted_{filename.replace('.zip', '')}"
        
        try:
            success, extracted = await extract_zip(str(file_path), str(extract_dir), check_safety=True)
        except ZipSafetyError as e:
            return f"⚠️ **ZIP Safety Check Failed:** {str(e)}"
        
        if not success:
            return f"❌ Extraction failed: {extracted[0] if extracted else 'Unknown error'}"
        
        # Move extracted files to user space and register them
        added_files = []
        for extracted_path in extracted:
            extracted_path = Path(extracted_path)
            new_filename = extracted_path.name
            new_path = user_dir / new_filename
            
            # Handle duplicates
            counter = 1
            while new_path.exists():
                stem = extracted_path.stem
                suffix = extracted_path.suffix
                new_filename = f"{stem}_{counter}{suffix}"
                new_path = user_dir / new_filename
                counter += 1
            
            os.rename(extracted_path, new_path)
            file_size = new_path.stat().st_size
            
            # Check if we can still upload
            can_upload, reason = await repo.can_upload(user_id, file_size)
            if can_upload:
                mime_type = mimetypes.guess_type(new_filename)[0] or 'application/octet-stream'
                await repo.add_file(
                    user_id=user_id,
                    filename=new_filename,
                    original_filename=extracted_path.name,
                    file_path=str(new_path),
                    file_size=file_size,
                    mime_type=mime_type
                )
                added_files.append(new_filename)
            else:
                os.remove(new_path)
        
        # Cleanup extraction directory
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir, ignore_errors=True)
        
        if added_files:
            file_list = "\n".join([f"• `{f}`" for f in added_files[:10]])
            if len(added_files) > 10:
                file_list += f"\n... and {len(added_files) - 10} more"
            return f"✅ **Extracted {len(added_files)} files from** `{filename}`:\n{file_list}"
        else:
            return f"⚠️ No files were extracted (storage limit may have been reached)"
        
    except Exception as e:
        logger.error(f"Failed to extract ZIP: {e}")
        return f"❌ Error extracting ZIP: {e}"


# ============================================================================
# FILE SHARING (FOR DISCORD)
# ============================================================================

async def get_file_for_discord(filename: str, **kwargs) -> Optional[tuple]:
    """
    Get a file from user space ready for Discord upload.
    
    This is an internal function used by the bot to send files to Discord.
    
    Returns:
        (BytesIO, filename) tuple or None
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return None
    
    try:
        repo = await _get_file_repo()
        
        file_info = await repo.get_file(user_id, filename)
        if not file_info:
            return None
        
        file_path = Path(file_info['file_path'])
        if not file_path.exists():
            return None
        
        async with aiofiles.open(file_path, 'rb') as f:
            data = await f.read()
        
        return BytesIO(data), filename
        
    except Exception as e:
        logger.error(f"Failed to get file for Discord: {e}")
        return None


async def share_file(filename: str, **kwargs) -> str:
    """
    Prepare a file from user's space for download/sharing.
    
    After calling this, the bot will send the file as a Discord attachment.
    
    Args:
        filename: Name of the file to share
    
    Returns:
        Confirmation message (the actual file is handled separately by the bot)
    """
    user_id = kwargs.get('user_id')
    if not user_id:
        return "Error: Could not determine user ID"
    
    try:
        repo = await _get_file_repo()
        
        file_info = await repo.get_file(user_id, filename)
        if not file_info:
            return f"❌ File not found: `{filename}`"
        
        file_path = Path(file_info['file_path'])
        if not file_path.exists():
            return f"❌ File missing from storage"
        
        # Update last_accessed - sharing means user is using the file
        await repo.update_last_accessed(user_id, filename)
        
        # Mark for sharing - the bot will handle the actual upload
        # We return a special token that the bot recognizes
        return f"__SHARE_FILE__:{filename}:{file_info['file_size']}"
        
    except Exception as e:
        logger.error(f"Failed to share file: {e}")
        return f"❌ Error sharing file: {e}"


# ============================================================================
# HELPERS
# ============================================================================

def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ============================================================================
# TOOL EXPORT
# ============================================================================

USER_SPACE_TOOLS = [
    save_to_space,
    upload_attachment_to_space,
    save_message_attachments,
    read_from_space,
    list_space,
    get_space_info,
    delete_from_space,
    zip_files,
    unzip_file,
    share_file,
]
