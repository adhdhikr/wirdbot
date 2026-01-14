import aiohttp
import logging
from typing import List, Dict, Any, Optional
from database import db

logger = logging.getLogger(__name__)

TRANSLATION_API_BASE = "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions"

LANGUAGE_EDITIONS = {
    'eng': 'eng-mustafakhattaba',
    'fra': 'fra-rashidmaash'
}

async def fetch_page_translations(page_number: int, language: str = 'eng') -> Optional[List[Dict[str, Any]]]:
    """Fetch translations for a specific page and language with caching."""
    
    # Try to get from cache first
    cached_data = await db.get_translation_cache(page_number, language)
    if cached_data:
        logger.debug(f"Translation cache hit for page {page_number}, language {language}")
        return cached_data
    
    # Cache miss - fetch from API
    logger.debug(f"Translation cache miss for page {page_number}, language {language} - fetching from API")
    edition = LANGUAGE_EDITIONS.get(language, LANGUAGE_EDITIONS['eng'])
    url = f"{TRANSLATION_API_BASE}/{edition}/pages/{page_number}.json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    translations = data.get('pages', [])
                    
                    # Cache the result
                    if translations:
                        await db.set_translation_cache(page_number, language, translations)
                        logger.debug(f"Cached translation for page {page_number}, language {language}")
                    
                    return translations
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