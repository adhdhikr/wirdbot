import aiohttp
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

TRANSLATION_API_BASE = "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions"

LANGUAGE_EDITIONS = {
    'eng': 'eng-mustafakhattaba',
    'fra': 'fra-rashidmaash'
}

async def fetch_page_translations(page_number: int, language: str = 'eng') -> Optional[List[Dict[str, Any]]]:
    """Fetch translations for a specific page and language."""
    edition = LANGUAGE_EDITIONS.get(language, LANGUAGE_EDITIONS['eng'])
    url = f"{TRANSLATION_API_BASE}/{edition}/pages/{page_number}.json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('pages', [])
                else:
                    logger.error(f"Failed to fetch translations for page {page_number}, language {language}: HTTP {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching translations for page {page_number}, language {language}: {e}")
        return None

async def format_translations(translations: List[Dict[str, Any]]) -> str:
    """Format the translations into a readable string."""
    if not translations:
        return "No translations available."

    formatted = []
    for verse in translations:
        chapter = verse.get('chapter', '?')
        verse_num = verse.get('verse', '?')
        text = verse.get('text', '').replace('`', '\\`')  # Escape backticks
        formatted.append(f"**{chapter}:{verse_num}** {text}")

    return "\n\n".join(formatted)