"""
Web search and URL reading tools.
Enhanced with search-in-page, link extraction, and smart content features.
"""
import asyncio
import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from ddgs import DDGS

logger = logging.getLogger(__name__)
MAX_CONTENT_LENGTH = 25000  # Max chars to return
REQUEST_TIMEOUT = 15  # seconds
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def _search_sync(query, max_results):
    """Synchronous wrapper for DDGS"""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


async def _fetch_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Fetch URL content. Returns (html, error)."""
    try:
        headers = {'User-Agent': USER_AGENT}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status != 200:
                    return None, f"HTTP {resp.status}"
                return await resp.text(), None
    except asyncio.TimeoutError:
        return None, "Request timed out"
    except Exception as e:
        return None, str(e)


def _clean_html(soup: BeautifulSoup) -> str:
    """Extract and clean text from BeautifulSoup object."""
    for element in soup(["script", "style", "nav", "footer", "header", "form", "aside", "iframe", "noscript"]):
        element.extract()
    
    text = soup.get_text(separator='\n')
    lines = [line.strip() for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


async def search_web(query: str, max_results: int = 5):
    """
    Search the web using DuckDuckGo.
    
    Use this to find current information, documentation, news, or answers.
    Follow up with read_url to get full content from promising results.
    
    Args:
        query: The search query
        max_results: Number of results (default 5, max 10)
    """
    try:
        max_results = min(int(max_results), 10)
        
        loop = asyncio.get_running_loop()
        
        for attempt in range(2):
            try:
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
            body = res.get('body', '')[:200]  # Trim snippet
            formatted += f"**{i}. [{title}]({href})**\n{body}\n\n"
        
        return formatted
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error searching web: {e}"


async def read_url(url: str, section: str = None):
    """
    Read the text content of a URL.
    
    Use this to read documentation, articles, or pages found via search.
    Optionally focus on a specific section by keyword.
    
    Args:
        url: The URL to read
        section: Optional keyword to focus on (returns content around that section)
    """
    try:
        html, error = await _fetch_url(url)
        if error:
            return f"Error: {error}"
        
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.title.string if soup.title else "No title"
        main_content = (
            soup.find('main') or 
            soup.find('article') or 
            soup.find('div', class_=re.compile(r'content|main|article', re.I)) or
            soup.body or 
            soup
        )
        
        text = _clean_html(main_content)
        if section:
            section_lower = section.lower()
            lines = text.split('\n')
            section_start = -1
            for i, line in enumerate(lines):
                if section_lower in line.lower():
                    section_start = max(0, i - 2)  # Include 2 lines before
                    break
            
            if section_start >= 0:
                focused = '\n'.join(lines[section_start:section_start + 100])
                text = f"[Focused on section containing '{section}']\n\n{focused}"
        
        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH] + f"\n\n... (Truncated to {MAX_CONTENT_LENGTH//1000}k chars)"
        
        return f"### {title}\n**URL:** {url}\n\n{text}"
    except Exception as e:
        logger.error(f"Read URL error: {e}")
        return f"Error reading URL: {e}"


async def search_in_url(url: str, search_term: str):
    """
    Search for specific text within a webpage.
    
    Returns all paragraphs/sections that contain the search term.
    Use this to find specific information within a long page.
    
    Args:
        url: The URL to search within
        search_term: The text to search for (case-insensitive)
    """
    try:
        html, error = await _fetch_url(url)
        if error:
            return f"Error: {error}"
        
        soup = BeautifulSoup(html, 'html.parser')
        text = _clean_html(soup)
        
        search_lower = search_term.lower()
        lines = text.split('\n')
        
        matches = []
        for i, line in enumerate(lines):
            if search_lower in line.lower():
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context = '\n'.join(lines[start:end])
                highlighted = re.sub(
                    f'({re.escape(search_term)})',
                    r'**\1**',
                    context,
                    flags=re.IGNORECASE
                )
                matches.append(highlighted)
        
        if not matches:
            return f"No matches found for '{search_term}' in {url}"
        unique_matches = []
        seen = set()
        for m in matches:
            key = m[:100]  # Use first 100 chars as key
            if key not in seen:
                seen.add(key)
                unique_matches.append(m)
        
        result = f"### Found {len(unique_matches)} matches for '{search_term}'\n\n"
        for i, match in enumerate(unique_matches[:15], 1):  # Max 15 matches
            result += f"**Match {i}:**\n{match}\n\n---\n\n"
        
        if len(unique_matches) > 15:
            result += f"... and {len(unique_matches) - 15} more matches"
        
        return result
    except Exception as e:
        logger.error(f"Search in URL error: {e}")
        return f"Error: {e}"


async def extract_links(url: str, filter_keyword: str = None):
    """
    Extract all links from a webpage.
    
    Useful for finding related pages, documentation links, or resources.
    Optionally filter links by a keyword.
    
    Args:
        url: The URL to extract links from
        filter_keyword: Optional keyword to filter links (matches URL or text)
    """
    try:
        html, error = await _fetch_url(url)
        if error:
            return f"Error: {error}"
        
        soup = BeautifulSoup(html, 'html.parser')
        
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)[:100] or "[No text]"
            if href.startswith('/'):
                from urllib.parse import urljoin
                href = urljoin(url, href)
            if href.startswith(('#', 'javascript:', 'mailto:')):
                continue
            if filter_keyword:
                if filter_keyword.lower() not in href.lower() and filter_keyword.lower() not in text.lower():
                    continue
            
            links.append({'text': text, 'url': href})
        
        if not links:
            return "No links found" + (f" matching '{filter_keyword}'" if filter_keyword else "")
        seen = set()
        unique_links = []
        for link in links:
            if link['url'] not in seen:
                seen.add(link['url'])
                unique_links.append(link)
        
        result = f"### Found {len(unique_links)} links"
        if filter_keyword:
            result += f" matching '{filter_keyword}'"
        result += "\n\n"
        
        for i, link in enumerate(unique_links[:30], 1):  # Max 30 links
            result += f"{i}. [{link['text']}]({link['url']})\n"
        
        if len(unique_links) > 30:
            result += f"\n... and {len(unique_links) - 30} more links"
        
        return result
    except Exception as e:
        logger.error(f"Extract links error: {e}")
        return f"Error: {e}"


async def get_page_headings(url: str):
    """
    Get all headings (h1-h6) from a webpage.
    
    Useful for understanding page structure before reading specific sections.
    
    Args:
        url: The URL to analyze
    """
    try:
        html, error = await _fetch_url(url)
        if error:
            return f"Error: {error}"
        
        soup = BeautifulSoup(html, 'html.parser')
        
        headings = []
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            for heading in soup.find_all(tag):
                text = heading.get_text(strip=True)
                if text:
                    headings.append({'level': tag, 'text': text[:150]})
        
        if not headings:
            return "No headings found on this page."
        
        result = f"### Page Structure ({len(headings)} headings)\n\n"
        for h in headings[:50]:  # Max 50 headings
            indent = "  " * (int(h['level'][1]) - 1)
            result += f"{indent}**{h['level'].upper()}:** {h['text']}\n"
        
        return result
    except Exception as e:
        logger.error(f"Get headings error: {e}")
        return f"Error: {e}"
WEB_TOOLS = [
    search_web,
    read_url,
    search_in_url,
    extract_links,
    get_page_headings,
]
