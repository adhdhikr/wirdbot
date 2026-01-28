"""
Web search and URL reading tools.
"""
import logging
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from ddgs import DDGS

logger = logging.getLogger(__name__)

def _search_sync(query, max_results):
    """Synchronous wrapper for DDGS"""
    with DDGS() as ddgs:
        # DDGS.text returns an iterator, convert to list
        return list(ddgs.text(query, max_results=max_results))

async def search_web(query: str, max_results: int = 5):
    """
    Search the web for information safely using DuckDuckGo.
    Use this to find real-time info, documentation, or answers.
    
    Args:
        query: The search query.
        max_results: Max results to return (default 5).
    """
    try:
        try:
             max_results = int(float(max_results))
        except:
             max_results = 5
             
        max_results = min(max_results, 10) # limit to 10
        
        loop = asyncio.get_running_loop()
        
        # Retry logic for DDG rate limits
        for attempt in range(2):
            try:
                # Run sync DDGS in a thread
                results = await loop.run_in_executor(None, _search_sync, query, max_results)
                break
            except Exception as e:
                if attempt == 1: 
                    logger.error(f"DDGS Error: {e}")
                    raise e
                await asyncio.sleep(1)
            
        if not results:
            return "No results found."
            
        formatted = ""
        for i, res in enumerate(results, 1):
            title = res.get('title', 'No Title')
            href = res.get('href', '#')
            body = res.get('body', '')
            formatted += f"{i}. [{title}]({href})\n  {body}\n"
            
        return formatted
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error searching web: {e}"

async def read_url(url: str):
    """
    Read the text content of a generic URL.
    Use this to read documentation, articles, or pages found via search.
    
    Args:
        url: The URL to read.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return f"Error: Status {resp.status}"
                
                html = await resp.text()
                
        soup = BeautifulSoup(html, 'html.parser')
        
        # Kill all script and style elements
        for script in soup(["script", "style", "nav", "footer", "header", "form"]):
            script.extract()    

        text = soup.get_text()
        
        # Clean text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        if len(text) > 20000:
            text = text[:20000] + "\n... (Truncated to 20k chars)"
            
        return f"### Content of {url}\n\n{text}"
    except Exception as e:
        logger.error(f"Read URL error: {e}")
        return f"Error reading URL: {e}"

# Export list
WEB_TOOLS = [
    search_web,
    read_url
]
