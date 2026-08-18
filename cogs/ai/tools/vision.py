"""
Vision tools for image analysis (OpenRouter vision models).
"""
import base64
import logging
import mimetypes
from pathlib import Path

from config import AI_VISION_MODEL

from ..llm import generate, reasoning_config

logger = logging.getLogger(__name__)

SUPPORTED_MIME = ("image/jpeg", "image/png", "image/webp", "image/gif")


async def analyze_image(image_input: str, question: str = "Describe this image in detail", **kwargs) -> str:
    """
    Analyzes an image using a vision model.

    Args:
        image_input: URL of the image OR a filename from your user space (e.g., "extracted_img1.png").
        question: The question to ask about the image.
        **kwargs: Context injected by the bot (user_id, model_name).
    """
    try:
        user_id = kwargs.get('user_id')
        image_data = None
        mime_type = "image/jpeg"
        image_url = None

        if image_input.startswith(('http://', 'https://')):
            # Pass the URL straight through — the provider fetches it itself.
            image_url = image_input
        elif user_id:
            filename = Path(image_input).name
            file_path = Path("data/user_files") / str(user_id) / filename

            if not file_path.exists():
                return f"❌ Error: Image file not found: `{filename}`"
            with open(file_path, "rb") as f:
                image_data = f.read()

            mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
        else:
            return "❌ Error: Invalid image input. Use a URL or a filename from your space."

        if image_url is None:
            if not image_data:
                return "❌ Error: Could not load image data."
            if mime_type not in SUPPORTED_MIME:
                mime_type = "image/jpeg"
            image_url = f"data:{mime_type};base64,{base64.b64encode(image_data).decode()}"

        prompt = question or "Describe this image in detail."
        # The chat model may be text-only, so vision always goes to AI_VISION_MODEL.
        model_name = kwargs.get('vision_model') or AI_VISION_MODEL

        response = await generate(
            model=model_name,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }],
            reasoning=reasoning_config("none"),
            max_tokens=2000,
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
