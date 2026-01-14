import aiohttp
import logging
from typing import List, Dict, Any, Optional
from utils.translation import fetch_page_translations
from database import db

logger = logging.getLogger(__name__)

TAFSIR_API_BASE = "https://cdn.jsdelivr.net/gh/spa5k/tafsir_api@main/tafsir"

TAFSIR_EDITIONS = {
    'en-tafisr-ibn-kathir': 'Tafsir Ibn Kathir (English)',
    'ar-tafsir-ibn-kathir': 'Tafsir Ibn Kathir (العربية)',
}

async def get_ayahs_for_page(page_number: int) -> List[Dict[str, Any]]:
    """Get all ayahs in a page using the translation API."""
    # Use English edition to get ayah structure
    translations = await fetch_page_translations(page_number, 'eng')
    if not translations:
        return []
    return translations

async def fetch_tafsir_for_ayah(edition: str, surah: int, ayah: int) -> Optional[str]:
    """Fetch tafsir for a specific ayah."""
    url = f"{TAFSIR_API_BASE}/{edition}/{surah}/{ayah}.json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('text', '')
                else:
                    logger.error(f"Failed to fetch tafsir for {edition}/{surah}/{ayah}: HTTP {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching tafsir for {edition}/{surah}/{ayah}: {e}")
        return None

async def fetch_page_tafsir(page_number: int, edition: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch tafsir for all ayahs in a page with caching."""
    
    # Try to get from cache first
    cached_data = await db.get_tafsir_cache(page_number, edition)
    if cached_data:
        logger.debug(f"Tafsir cache hit for page {page_number}, edition {edition}")
        return cached_data
    
    # Cache miss - fetch from API
    logger.debug(f"Tafsir cache miss for page {page_number}, edition {edition} - fetching from API")
    ayahs = await get_ayahs_for_page(page_number)
    if not ayahs:
        return None

    tafsir_data = []
    for ayah in ayahs:
        surah = ayah.get('chapter')
        ayah_num = ayah.get('verse')
        if surah and ayah_num:
            tafsir_text = await fetch_tafsir_for_ayah(edition, surah, ayah_num)
            if tafsir_text:
                tafsir_data.append({
                    'surah': surah,
                    'ayah': ayah_num,
                    'text': tafsir_text
                })

    # Cache the result
    if tafsir_data:
        await db.set_tafsir_cache(page_number, edition, tafsir_data)
        logger.debug(f"Cached tafsir for page {page_number}, edition {edition}")
    
    return tafsir_data if tafsir_data else None

async def format_tafsir(tafsir_data: List[Dict[str, Any]]) -> str:
    """Format tafsir data into a readable string."""
    if not tafsir_data:
        return "No tafsir available."

    formatted = []
    for item in tafsir_data:
        surah = item.get('surah', '?')
        ayah = item.get('ayah', '?')
        text = item.get('text', '').replace('`', '\\`')  # Escape backticks
        formatted.append(f"**{surah}:{ayah}**\n{text}")

    return "\n\n".join(formatted)