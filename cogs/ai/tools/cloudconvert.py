"""
CloudConvert Tools
AI-callable tools for file conversion using CloudConvert API.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import nextcord as discord
import requests

from config import CLOUDCONVERT_API_KEY

logger = logging.getLogger(__name__)
API_BASE = "https://api.cloudconvert.com/v2"
USER_FILES_BASE = Path("data/user_files")


def _get_user_dir(user_id: int) -> Path:
    """Get the storage directory for a user."""
    user_dir = USER_FILES_BASE / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    filename = os.path.basename(filename)
    dangerous_chars = ['..', '/', '\\', '\x00']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    return filename or 'unnamed_file'


def _upload_file_to_task_sync(file_path: str, import_task: dict, api_key: str) -> str:
    """Synchronously upload a file using CloudConvert's S3 form upload."""
    if 'result' not in import_task or 'form' not in import_task['result']:
        raise ValueError("Import task does not have upload form")
    
    form = import_task['result']['form']
    url = form['url']
    fields = form['parameters'].copy()
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, data=fields, files=files)
    
    response.raise_for_status()
    return response.text


def _create_job_sync(output_format: str, api_key: str) -> dict:
    """Synchronously create a conversion job with import task."""
    job_data = {
        "tasks": {
            "import": {
                "operation": "import/upload"
            },
            "convert": {
                "operation": "convert",
                "input": "import",
                "output_format": output_format
            },
            "export": {
                "operation": "export/url",
                "input": "convert"
            }
        }
    }
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.post(f"{API_BASE}/jobs", json=job_data, headers=headers)
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create job: {e}\nResponse: {response.text}")
        raise
    return response.json()


def _check_job_status_sync(job_id: str, api_key: str) -> dict:
    """Synchronously check job status."""
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(f"{API_BASE}/jobs/{job_id}", headers=headers)
    response.raise_for_status()
    return response.json()


def _delete_job_sync(job_id: str, api_key: str) -> bool:
    """Synchronously delete a job. Returns True if successful."""
    try:
        headers = {'Authorization': f'Bearer {api_key}'}
        response = requests.delete(f"{API_BASE}/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        logger.info(f"✅ Successfully deleted job {job_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to delete job {job_id}: {e}")
        return False


def _download_file_sync(download_url: str, output_path: str) -> None:
    """Synchronously download a file from URL to local path."""
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    logger.info(f"✅ Downloaded file to {output_path}")


def _check_api_status_sync(api_key: str) -> dict:
    """Check CloudConvert API key and account status."""
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(f"{API_BASE}/user", headers=headers)
    response.raise_for_status()
    return response.json()


async def check_cloudconvert_status(**kwargs) -> str:
    """
    Check your CloudConvert API key and account status.
    
    This will show your credits, plan, and any billing issues.
    
    Returns:
        Account status information
    """
    if not CLOUDCONVERT_API_KEY:
        return "❌ Error: CloudConvert API key not configured. Please set CLOUDCONVERT_API_KEY in your .env file"
    
    try:
        loop = asyncio.get_running_loop()
        
        user_info = await loop.run_in_executor(
            None, _check_api_status_sync, CLOUDCONVERT_API_KEY
        )
        username = user_info.get('data', {}).get('username', 'Unknown')
        email = user_info.get('data', {}).get('email', 'Unknown')
        credits = user_info.get('data', {}).get('credits', 0)
        plan = user_info.get('data', {}).get('plan', 'Unknown')
        
        status_msg = "🔍 **CloudConvert Account Status**\n"
        status_msg += f"👤 Username: `{username}`\n"
        status_msg += f"📧 Email: `{email}`\n"
        status_msg += f"💰 Credits: `{credits}`\n"
        status_msg += f"📋 Plan: `{plan}`\n"
        
        if credits == 0:
            status_msg += "\n⚠️ **Warning**: You have 0 credits remaining!\n"
            status_msg += "💡 Visit https://cloudconvert.com/dashboard to add credits."
        elif credits < 10:
            status_msg += f"\n⚠️ **Low Credits**: Only {credits} remaining."
        logger.info(f"🔍 CloudConvert User Info: {user_info}")
        
        return status_msg
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API status check failed: {e}")
        error_details_str = ""
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response headers: {dict(e.response.headers)}")
            try:
                error_details = e.response.json()
                logger.error(f"Response body: {error_details}")
                error_details_str = f"\n📄 **Full Error Response:**\n```json\n{error_details}\n```"
            except Exception:
                logger.error(f"Response text: {e.response.text}")
                error_details_str = f"\n📄 **Error Response:**\n```\n{e.response.text}\n```"
        
        return f"❌ Failed to check API status: {e}{error_details_str}"


async def convert_file(filename: str, output_format: str, output_filename: Optional[str] = None, **kwargs) -> str:
    """
    Convert a file from your personal space using CloudConvert API.
    
    Supports various file formats like PDF, DOCX, images, etc.
    The file must exist in your personal file space.
    
    Upon successful conversion, the file will be automatically uploaded to Discord and you'll be mentioned.
    
    Args:
        filename: Name of the file in your space to convert
        output_format: Target format (e.g., 'pdf', 'docx', 'jpg', 'png')
        output_filename: Optional output filename (defaults to input name with new extension)
    
    Returns:
        Success message with output file path
    """
    user_id = kwargs.get('user_id')
    channel = kwargs.get('channel')
    
    if not user_id:
        return "❌ Error: Could not determine user ID"
    
    if not CLOUDCONVERT_API_KEY:
        return "❌ Error: CloudConvert API key not configured. Please set CLOUDCONVERT_API_KEY in your .env file"
    status_msg = None
    if channel:
        status_msg = await channel.send("🔄 Calling CloudConvert...")
    
    job_id = None  # Initialize job_id for cleanup tracking
    
    try:
        user_dir = _get_user_dir(user_id)
        filename = _sanitize_filename(filename)
        input_path = user_dir / filename
        if not input_path.exists():
            error_msg = f"❌ Error: File '{filename}' not found in your space. Use 'list_space' to see available files."
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        file_size = input_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        if not output_filename:
            output_filename = input_path.stem + f".{output_format}"
        output_filename = _sanitize_filename(output_filename)
        output_path = user_dir / output_filename
        if output_path == input_path:
            error_msg = "❌ Error: Output filename cannot be the same as input filename"
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        
        logger.info(f"🚀 Starting conversion: {filename} ({file_size_mb:.1f}MB) -> {output_filename}")
        if status_msg:
            await status_msg.edit(content=f"✅ Started conversion: `{filename}` ({file_size_mb:.1f}MB) → `{output_filename}`\n🔄 Converting in background...")
        
        print(f"📁 Converting: {filename} ({file_size_mb:.1f}MB) to {output_format}")
        
        loop = asyncio.get_running_loop()
        print("⚙️  Step 1/4: Creating conversion job...")
        logger.info(f"⚙️ Creating conversion job: {filename} -> {output_format}")
        
        try:
            job_result = await loop.run_in_executor(
                None, _create_job_sync, output_format, CLOUDCONVERT_API_KEY
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Job creation failed: {e}")
            error_details_str = ""
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response headers: {dict(e.response.headers)}")
                try:
                    error_details = e.response.json()
                    logger.error(f"Response body: {error_details}")
                    error_details_str = f"\n📄 **Full Error Response:**\n```json\n{error_details}\n```"
                except Exception:
                    logger.error(f"Response text: {e.response.text}")
                    error_details_str = f"\n📄 **Error Response:**\n```\n{e.response.text}\n```"
            
            error_msg = f"❌ Failed to create conversion job: {e}"
            if "Payment Required" in str(e):
                error_msg += "\n💳 **Payment/Billing Issue**: Check your CloudConvert account credits or billing settings."
            error_msg += error_details_str
            
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        
        job_id = job_result['data']['id']
        logger.info(f"🔍 CloudConvert Job Creation Response: {job_result}")
        
        logger.info(f"✅ Job created: {job_id}")
        print("✅ Conversion job created (25% done)")
        import_task = None
        for task in job_result['data']['tasks']:
            if task['operation'] == 'import/upload':
                import_task = task
                break
        
        if not import_task:
            error_msg = "❌ Job created but no import task found"
            if job_id:
                try:
                    await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                    logger.info(f"🧹 Cleaned up job {job_id} due to missing import task")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        
        import_task_id = import_task['id']
        logger.info(f"📤 Import task ID: {import_task_id}")
        print("⏳ Waiting for upload form...")
        logger.info("⏳ Waiting for import task to provide upload form...")
        
        import_task_ready = None
        form_ready_attempts = 0
        max_form_attempts = 12  # 1 minute max
        
        while form_ready_attempts < max_form_attempts:
            await asyncio.sleep(5)
            
            try:
                status_result = await loop.run_in_executor(
                    None, _check_job_status_sync, job_id, CLOUDCONVERT_API_KEY
                )
            except requests.exceptions.RequestException as e:
                logger.error(f"Status check failed: {e}")
                continue
            current_import_task = None
            for task in status_result['data']['tasks']:
                if task['id'] == import_task_id:
                    current_import_task = task
                    break
            
            if current_import_task and 'result' in current_import_task and 'form' in current_import_task['result']:
                import_task_ready = current_import_task
                logger.info("✅ Upload form ready")
                break
            
            form_ready_attempts += 1
            logger.info(f"⏳ Still waiting for upload form... ({form_ready_attempts}/{max_form_attempts})")
        
        if not import_task_ready:
            error_msg = "❌ Import task did not provide upload form within timeout"
            if job_id:
                try:
                    await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                    logger.info(f"🧹 Cleaned up job {job_id} due to import task timeout")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        print("⬆️  Step 2/4: Uploading file to CloudConvert...")
        logger.info(f"⬆️ Uploading {input_path} ({file_size_mb:.1f}MB) using S3 form upload")
        
        try:
            upload_result = await loop.run_in_executor(
                None, _upload_file_to_task_sync, str(input_path), import_task_ready, CLOUDCONVERT_API_KEY
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Upload failed: {e}")
            error_msg = f"❌ Upload failed: {e}"
            if job_id:
                try:
                    await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                    logger.info(f"🧹 Cleaned up job {job_id} due to upload failure")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        logger.info(f"🔍 CloudConvert S3 Upload Response: {upload_result}")
        
        logger.info("✅ Upload successful")
        print("✅ Upload complete (50% done)")
        print("⏳ Step 3/4: Processing file (this may take several minutes)...")
        logger.info("⏳ Waiting for conversion to complete...")
        
        max_attempts = 60  # 5 minutes max
        attempt = 0
        
        while attempt < max_attempts:
            await asyncio.sleep(5)  # Wait 5 seconds
            
            try:
                status_result = await loop.run_in_executor(
                    None, _check_job_status_sync, job_id, CLOUDCONVERT_API_KEY
                )
            except requests.exceptions.RequestException as e:
                logger.error(f"Status check failed: {e}")
                error_msg = f"❌ Failed to check conversion status: {e}"
                if job_id:
                    try:
                        await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                        logger.info(f"🧹 Cleaned up job {job_id} due to status check failure")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
                if status_msg:
                    await status_msg.edit(content=error_msg)
                return error_msg
            
            status = status_result['data']['status']
            logger.info(f"🔍 CloudConvert API Response: {status_result}")
            
            logger.info(f"📊 Job status: {status}")
            elapsed_time = attempt * 5
            progress = min(100, 50 + (elapsed_time / 300) * 50)  # 50-100% range
            
            if status == 'finished':
                print("✅ Conversion completed (100% done)")
                break
            elif status == 'error':
                error_msg = status_result['data'].get('message', 'Unknown error')
                logger.error(f"Conversion failed: {error_msg}")
                error_response = f"❌ Conversion failed: {error_msg}"
                if job_id:
                    try:
                        await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                        logger.info(f"🧹 Cleaned up failed job {job_id}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
                if status_msg:
                    await status_msg.edit(content=error_response)
                return error_response
            elif status == 'processing':
                if elapsed_time % 30 == 0 and elapsed_time > 0:
                    print(f"🔄 Still processing... ({int(progress)}% complete, {elapsed_time}s elapsed)")
            elif attempt == 0:
                print(f"🔄 Job status: {status}")
            
            attempt += 1
        
        if attempt >= max_attempts:
            logger.error("Conversion timed out")
            error_msg = "❌ Conversion timed out after 5 minutes. Please try again or contact support."
            if job_id:
                try:
                    await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                    logger.info(f"🧹 Cleaned up timed out job {job_id}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        print("⬇️  Step 4/4: Downloading converted file...")
        logger.info("⬇️ Downloading converted file...")
        
        export_task = None
        for task in status_result['data']['tasks']:
            if task['operation'] == 'export/url' and task['status'] == 'finished':
                export_task = task
                break
        
        if not export_task:
            logger.error("No export URL found")
            error_msg = "❌ Conversion completed but no download URL found. Please contact support."
            if job_id:
                try:
                    await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                    logger.info(f"🧹 Cleaned up job {job_id} due to missing export URL")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        
        download_url = export_task['result']['files'][0]['url']
        logger.info(f"✅ Download URL obtained: {download_url}")
        
        try:
            await loop.run_in_executor(
                None, _download_file_sync, download_url, str(output_path)
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Download failed: {e}")
            error_msg = f"❌ Failed to download converted file: {e}"
            if job_id:
                try:
                    await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                    logger.info(f"🧹 Cleaned up job {job_id} due to download failure")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        if not output_path.exists():
            logger.error("Output file not created")
            error_msg = "❌ Converted file was not saved properly. Please contact support."
            if job_id:
                try:
                    await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                    logger.info(f"🧹 Cleaned up job {job_id} due to file save failure")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
            if status_msg:
                await status_msg.edit(content=error_msg)
            return error_msg
        
        output_size = output_path.stat().st_size
        output_size_mb = output_size / (1024 * 1024)
        
        logger.info(f"✅ Conversion successful: {output_path} ({output_size_mb:.1f}MB)")
        print("🎉 Conversion complete!")
        if channel:
            try:
                discord_file = discord.File(output_path, filename=output_filename)
                user_mention = f"<@{user_id}>"
                await channel.send(
                    content=f"{user_mention} ✅ **File conversion completed!**\n📁 `{output_filename}` ({output_size_mb:.1f}MB)",
                    file=discord_file
                )
                logger.info(f"✅ Uploaded converted file to Discord: {output_filename}")
            except Exception as upload_error:
                logger.error(f"Failed to upload file to Discord: {upload_error}")
                await channel.send(f"<@{user_id}> ✅ **Conversion successful!**\n📁 File: `{output_filename}`\n📊 Size: {output_size_mb:.1f}MB\n💡 Use `read_from_space` or `share_file` to access it.")
        
        success_msg = f"✅ **Conversion successful!**\n📁 File: `{output_filename}`\n📊 Size: {output_size_mb:.1f}MB\n💡 You can now use `read_from_space` or `share_file` with this file."
        
        if status_msg:
            await status_msg.edit(content=success_msg)
        
        return success_msg
        
    except requests.exceptions.RequestException as e:
        logger.error(f"CloudConvert API error: {e}")
        error_msg = f"❌ API error: {e}"
        if job_id:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                logger.info(f"🧹 Cleaned up job {job_id} due to API error")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
        if status_msg:
            await status_msg.edit(content=error_msg)
        return error_msg
    except Exception as e:
        logger.error(f"Unexpected conversion error: {e}")
        error_msg = f"❌ Unexpected error: {e}"
        if job_id:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _delete_job_sync, job_id, CLOUDCONVERT_API_KEY)
                logger.info(f"🧹 Cleaned up job {job_id} due to unexpected error")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup job {job_id}: {cleanup_error}")
        if status_msg:
            await status_msg.edit(content=error_msg)
        return error_msg
CLOUDCONVERT_TOOLS = [
    convert_file,
    check_cloudconvert_status,
]