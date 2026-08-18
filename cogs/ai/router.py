"""
Model selection.

By default one model (AI_MODEL) answers everything. Setting
AI_ROUTING_ENABLED=true turns on the two-tier setup instead: a cheap classifier
labels each message SIMPLE or COMPLEX and picks the matching model.
"""
import logging

from config import (
    AI_COMPLEX_MODEL,
    AI_COMPLEX_REASONING,
    AI_MODEL,
    AI_REASONING,
    AI_ROUTER_MODEL,
    AI_ROUTING_ENABLED,
    AI_SIMPLE_MODEL,
    AI_SIMPLE_REASONING,
)

from .llm import generate, reasoning_config

logger = logging.getLogger(__name__)

ROUTING_ENABLED = AI_ROUTING_ENABLED
DEFAULT_MODEL = AI_MODEL
EVALUATOR_MODEL = AI_ROUTER_MODEL
SIMPLE_MODEL = AI_SIMPLE_MODEL
COMPLEX_MODEL = AI_COMPLEX_MODEL

# Reasoning ("thinking") budget per model — see config.py to tune via .env.
REASONING = {
    DEFAULT_MODEL: reasoning_config(AI_REASONING),
    SIMPLE_MODEL: reasoning_config(AI_SIMPLE_REASONING),
    COMPLEX_MODEL: reasoning_config(AI_COMPLEX_REASONING),
}


def reasoning_for(model: str) -> dict:
    """Reasoning config for a model, defaulting to AI_REASONING."""
    return REASONING.get(model, reasoning_config(AI_REASONING))


def thinks(model: str) -> bool:
    """Whether this model will actually produce a chain of thought."""
    return bool(reasoning_for(model).get('enabled'))


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


async def select_model(message_content: str, image_context: str = "") -> str:
    """
    Pick the model for one message.

    With routing off this is just AI_MODEL. With routing on, "use pro" /
    "use flash" in the message force a tier, very short messages skip the
    classifier, and anything else gets classified.
    """
    if not ROUTING_ENABLED:
        return DEFAULT_MODEL

    lowered = (message_content or "").lower()
    if any(kw in lowered for kw in ("use pro", "force pro", "pro model", "pro brain", "big model", "think hard")):
        complexity = "COMPLEX"
    elif any(kw in lowered for kw in ("use flash", "force flash", "flash model", "fast model", "small model")):
        complexity = "SIMPLE"
    elif len(message_content or "") < 100 and not image_context:
        complexity = "SIMPLE"
    else:
        complexity = await evaluate_complexity(f"{message_content}{image_context}")

    model = COMPLEX_MODEL if complexity == "COMPLEX" else SIMPLE_MODEL
    logger.info(f"Smart Routing: {complexity} -> {model}")
    return model
