import aiohttp
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

API_BASE_URL = "http://api.alquran.cloud/v1"

async def get_ayah(reference: str, edition: str = 'quran-uthmani') -> str:
    """
    Get an ayah by reference (e.g., "2:255" or "262") and edition.
    """
    url = f"{API_BASE_URL}/ayah/{reference}/{edition}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'OK':
                        text = data['data'].get('text', '')
                        # If audio, returns URL? The user prompt said audio returns recitation.
                        # We focus on text for now as per prompt "Only text editions...".
                        return text
                    else:
                        return f"Error: {data.get('data')}"
                else:
                    return f"Error: HTTP {response.status}"
    except Exception as e:
        logger.error(f"Error fetching ayah {reference}: {e}")
        return f"Error: {e}"

async def get_page(page: int, edition: str = 'quran-uthmani') -> str:
    """
    Get a full page of the Quran.
    """
    url = f"{API_BASE_URL}/page/{page}/{edition}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'OK':
                        # The API returns 'ayahs' list in data['data']['ayahs'] usually for page endpoint?
                        # Let's check the user provided example structure implicitly. 
                        # Assuming standard response structure for alquran.cloud
                        result = []
                        ayahs = data['data'].get('ayahs', [])
                        for ayah in ayahs:
                            surah = ayah.get('surah', {}).get('number')
                            num = ayah.get('numberInSurah')
                            text = ayah.get('text', '')
                            result.append(f"[{surah}:{num}] {text}")
                        return "\n".join(result)
                    else:
                        return f"Error: {data.get('data')}"
                else:
                    return f"Error: HTTP {response.status}"
    except Exception as e:
        logger.error(f"Error fetching page {page}: {e}")
        return f"Error: {e}"

async def search_quran(keyword: str, surah: str = 'all', edition: str = 'quran-uthmani', language: str = 'en') -> str:
    """
    Search the Quran text.
    """
    # URL structure: http://api.alquran.cloud/v1/search/{{keyword}}/{{surah}}/{{edition or language}}
    # User said: If you do not specify an edition or language, all english language texts are searched.
    # We will prefer edition if provided, else language.
    
    target = edition
    if not edition or edition == 'quran-uthmani': # If default, maybe user wants english search?
        # But if keyword is arabic? 
        # Let's trust the args. If user says edition='en.pickthall', use it.
        pass

    url = f"{API_BASE_URL}/search/{keyword}/{surah}/{target}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'OK':
                        matches = data['data'].get('matches', [])
                        if not matches:
                            return "No matches found."
                        
                        # Limit to reasonable amount
                        formatted = []
                        count = data['data'].get('count', len(matches))
                        
                        for m in matches[:10]: # Limit to 10
                            surah_num = m.get('surah', {}).get('number')
                            ayah_num = m.get('numberInSurah')
                            text = m.get('text', '')
                            edition_name = m.get('edition', {}).get('name', '')
                            formatted.append(f"**[{surah_num}:{ayah_num}]** {text} ({edition_name})")
                        
                        output = f"Found {count} matches (Showing top 10):\n\n" + "\n\n".join(formatted)
                        if count > 10:
                            output += f"\n\n... and {count - 10} more."
                        return output
                    else:
                        return f"Error: {data.get('data')}"
                else:
                    return f"Error: HTTP {response.status}"
    except Exception as e:
        logger.error(f"Error searching quran for {keyword}: {e}")
        return f"Error: {e}"
