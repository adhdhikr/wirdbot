"""
Router module for Intelligent Model Switching.
Evaluates query complexity to select the best model.
"""
import logging

from config import (
    AI_COMPLEX_MODEL,
    AI_COMPLEX_REASONING,
    AI_ROUTER_MODEL,
    AI_SIMPLE_MODEL,
    AI_SIMPLE_REASONING,
)

from .llm import generate, reasoning_config

logger = logging.getLogger(__name__)
EVALUATOR_MODEL = AI_ROUTER_MODEL
SIMPLE_MODEL = AI_SIMPLE_MODEL
COMPLEX_MODEL = AI_COMPLEX_MODEL

# Reasoning ("thinking") budget per tier — see config.py to tune via .env.
REASONING = {
    SIMPLE_MODEL: reasoning_config(AI_SIMPLE_REASONING),
    COMPLEX_MODEL: reasoning_config(AI_COMPLEX_REASONING),
}


def reasoning_for(model: str) -> dict:
    """Reasoning config for a model, defaulting to the simple tier's budget."""
    return REASONING.get(model, reasoning_config(AI_SIMPLE_REASONING))


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
        response = await generate(
            model=EVALUATOR_MODEL,
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": f"User Message: {text}"},
            ],
            reasoning=reasoning_config("none"),  # classification needs no thinking
            temperature=0.0,  # deterministic
            max_tokens=16,
        )

        if response.text:
            result = response.text.strip().upper()
            if "COMPLEX" in result:
                return "COMPLEX"

        return "SIMPLE"

    except Exception as e:
        logger.error(f"Router evaluation failed: {e}")
        return "SIMPLE"
