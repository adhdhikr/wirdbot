"""
Vision tools for image analysis using Gemini.
"""
import logging
import aiohttp
import io
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

async def analyze_image(url: str, question: str = "Describe this image in detail", **kwargs) -> str:
    """
    Analyzes an image from a URL using Gemini Vision.
    
    Args:
        url: The URL of the image to analyze.
        question: The question to ask about the image (default: "Describe this image").
        **kwargs: Context injected by the bot (e.g., 'model_name').
    """
    try:
        # 1. Download Image
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return f"Error downloading image: Status {resp.status}"
                image_data = await resp.read()
                
        # 2. Determine Model (from kwargs or default)
        model_name = kwargs.get('model_name', 'gemini-3-flash-preview')
        
        # 3. Call Gemini API
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Determine prompt based on question
        prompt = question
        if not prompt: prompt = "Describe this image in detail."
        
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type="image/jpeg"), # Assuming JPEG/PNG logic auto-handling or generic
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
