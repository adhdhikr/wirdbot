"""
Quran and Tafsir related tools for the AI cog.
"""
import logging
import io
import aiohttp
from config import API_BASE_URL
from utils.tafsir import fetch_tafsir_for_ayah, TAFSIR_EDITIONS
from utils.translation import fetch_page_translations
from utils.quran import get_ayah, get_page, search_quran

logger = logging.getLogger(__name__)


async def lookup_quran_page(page_number: int):
    """
    Get the English translation/text for a specific Quran page.
    Args:
        page_number: The page number (1-604).
    """
    try:
        page_number = int(float(page_number))
    except ValueError:
        return "Invalid page number."

    translations = await fetch_page_translations(page_number, 'eng')
    if not translations:
        return "Page not found or error fetching."
    
    result = ""
    for v in translations:
        result += f"[{v.get('chapter')}:{v.get('verse')}] {v.get('text')}\n"
    return result


async def lookup_tafsir(surah: int, ayah: int, edition: str = 'en-tafisr-ibn-kathir', segment: int = 0):
    """
    Get the Tafsir (exegesis) for a specific verse.
    Args:
        surah: Surah number.
        ayah: Ayah number.
        edition: 'en-tafisr-ibn-kathir' (default), 'ar-tafsir-ibn-kathir', 'en-al-jalalayn', or 'en-tafsir-maarif-ul-quran'.
        segment: The part number to retrieve (default 0). If text is long, request segment=1, 2, etc.
    """
    try:
        surah = int(float(surah))
        ayah = int(float(ayah))
        segment = int(float(segment))
    except (ValueError, TypeError):
        return "Invalid input parameters."

    try:
        text = await fetch_tafsir_for_ayah(edition, surah, ayah)
    except Exception as e:
        return f"Error calling fetch_tafsir_for_ayah: {e}"

    if not text:
        return "Tafsir not found."

    edition_name = TAFSIR_EDITIONS.get(edition, edition)
    attribution = f"\n\n**Source:** {edition_name}"
    full_text = text + attribution

    chunk_size = 1800
    chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
    
    if segment >= len(chunks):
        return "No more text available in this tafsir."
        
    result = chunks[segment]
    
    if segment < len(chunks) - 1:
        result += f"\n\n[SYSTEM: This is part {segment+1} of {len(chunks)}. To read the next part, call lookup_tafsir(..., segment={segment+1}). Tell the user there is more.]"
        
    return result


async def show_quran_page(page_number: int, **kwargs):
    """
    Uploads the image of a specific Quran page to the chat.
    Use this when the user asks to SEE the page.
    
    Args:
        page_number: The page number (1-604).
    """
    import nextcord as discord
    
    channel = kwargs.get('channel')
    if not channel:
        return "Error: Cannot upload image without channel context."
        
    # Get mushaf_type from config if available (passed in kwargs or default)
    mushaf_type = kwargs.get('mushaf_type', 'madani')

    try:
        page_number = int(float(page_number))
    except (ValueError, TypeError):
        return "Invalid page number."
    
    url = f"{API_BASE_URL}/mushaf/{mushaf_type}/page/{page_number}"
    logger.info(f"Fetching Quran page image from: {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = io.BytesIO(await resp.read())
                    file = discord.File(data, filename=f"page_{page_number}.png")
                    await channel.send(content=f"**Page {page_number}** ({mushaf_type})", file=file)
                    return f"Successfully uploaded image of page {page_number}."
                else:
                    logger.error(f"Failed to fetch image {url}: {resp.status}")
                    return f"Failed to fetch image (status {resp.status})."
    except Exception as e:
        logger.error(f"Error sending Quran page image: {e}")
        return f"Error sending image: {e}"


async def get_ayah_safe(surah: int, ayah: int, edition: str = 'quran-uthmani'):
    """
    Get a specific Ayah (Verse). Wrapper for type safety.
    Args:
        surah: Surah number.
        ayah: Ayah number.
        edition: The edition/translation (default 'quran-uthmani').
    """
    try:
        surah = int(float(surah))
        ayah = int(float(ayah))
        ref = f"{surah}:{ayah}"
        try:
            return await get_ayah(ref, edition)
        except Exception as e:
            return f"Error calling get_ayah('{ref}', '{edition}'): {e}"
    except (ValueError, TypeError):
        return "Invalid Surah or Ayah number."


async def get_page_safe(page: int, edition: str = 'quran-uthmani'):
    """
    Get a full Quran page text. Wrapper for type safety.
    Args:
        page: Page number (1-604).
        edition: Edition to retrieve.
    """
    try:
        page = int(float(page))
        return await get_page(page, edition)
    except (ValueError, TypeError):
        return "Invalid page number."


async def search_quran_safe(keyword: str, surah: str = 'all', edition: str = 'quran-uthmani', language: str = 'en'):
    """
    Search the Quran. Wrapper to clean inputs.
    Args:
        keyword: The search term.
        surah: Surah number or 'all'.
        edition: Edition to search.
        language: Language code.
    """
    if str(surah).lower() != 'all':
        try:
            surah = str(int(float(surah)))
        except:
            pass  # Keep as is if not a number
            
    return await search_quran(keyword, surah, edition, language)


# Export list
QURAN_TOOLS = [
    lookup_quran_page,
    lookup_tafsir,
    show_quran_page,
    get_ayah_safe,
    get_page_safe,
    search_quran_safe,
]
