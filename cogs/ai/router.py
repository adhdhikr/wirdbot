"""
Router module for Intelligent Model Switching.
Evaluates query complexity to select the best model.
"""
import logging

from google import genai

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)
EVALUATOR_MODEL = "gemini-2.5-flash-lite"
SIMPLE_MODEL = "gemini-3-flash-preview"
COMPLEX_MODEL = "gemini-3-pro-preview"

ROUTER_PROMPT = """
You are a request classifier. Classify the following user message as 'SIMPLE' or 'COMPLEX'.

CRITERIA:
- **COMPLEX**: Advanced Math, Physics problems, Large/Complex Coding tasks (algorithms, architecture, optimization), complex reasoning puzzles, or when explicitly requested.
- **SIMPLE**: Everything else. This includes: General conversation, Discord actions, Web search, simple bot commands, simple questions, summaries.

Output ONLY 'SIMPLE' or 'COMPLEX'.
"""

async def evaluate_complexity(text: str) -> str:
    """
    Evaluates the complexity of a user query using a fast model.
    Returns: 'SIMPLE' or 'COMPLEX'
    """
    if not text or len(text.strip()) < 20: 
        return "SIMPLE"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = await client.aio.models.generate_content(
            model=EVALUATOR_MODEL,
            contents=[ROUTER_PROMPT, f"User Message: {text}"],
            config={"temperature": 0.0} # Deterministic
        )
        
        if response.text:
            result = response.text.strip().upper()
            if "COMPLEX" in result:
                return "COMPLEX"
                
        return "SIMPLE"
        
    except Exception as e:
        logger.error(f"Router evaluation failed: {e}")
        return "SIMPLE"
