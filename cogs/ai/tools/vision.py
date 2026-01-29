"""
Vision tools for image analysis using Gemini.
"""
import logging
import aiohttp
import io
import mimetypes
from pathlib import Path
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

async def analyze_image(image_input: str, question: str = "Describe this image in detail", **kwargs) -> str:
    """
    Analyzes an image using Gemini Vision.
    
    Args:
        image_input: URL of the image OR a filename from your user space (e.g., "extracted_img1.png").
        question: The question to ask about the image.
        **kwargs: Context injected by the bot (user_id, model_name).
    """
    try:
        user_id = kwargs.get('user_id')
        image_data = None
        mime_type = "image/jpeg"
        
        # Case 1: URL
        if image_input.startswith(('http://', 'https://')):
            async with aiohttp.ClientSession() as session:
                async with session.get(image_input) as resp:
                    if resp.status != 200:
                        return f"Error downloading image: Status {resp.status}"
                    image_data = await resp.read()
                    content_type = resp.headers.get('Content-Type')
                    if content_type:
                        mime_type = content_type
        
        # Case 2: Local Filename (User Space)
        elif user_id:
            # Resolve file path safely
            # Avoid circular import by accessing DB directly or standard path
            # Standard path: data/user_files/<user_id>/<filename>
            
            # Simple sanitization
            filename = Path(image_input).name
            file_path = Path("data/user_files") / str(user_id) / filename
            
            if not file_path.exists():
                return f"❌ Error: Image file not found: `{filename}`"
            
            # Read file
            with open(file_path, "rb") as f:
                image_data = f.read()
            
            mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
            
        else:
            return "❌ Error: Invalid image input. Use a URL or a filename from your space."

        if not image_data:
            return "❌ Error: Could not load image data."

        # 2. Determine Model (from kwargs or default)
        model_name = kwargs.get('model_name', 'gemini-3-flash-preview')
        
        # 3. Call Gemini API
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Determine prompt based on question
        prompt = question
        if not prompt: prompt = "Describe this image in detail."
        
        # Ensure mime_type is valid for Gemini (jpeg, png, webp, heic)
        # If it's something else, try to send as jpeg and hope
        if mime_type not in ["image/jpeg", "image/png", "image/webp", "image/heic"]:
             mime_type = "image/jpeg"

        response = await client.aio.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type=mime_type),
                        types.Part.from_text(text=prompt)
                    ]
                )
            ]
        )
        
        if response.text:
            return response.text
            
        return "No analysis returned."
        
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return f"Error analyzing image: {e}"

VISION_TOOLS = [
    analyze_image
]
