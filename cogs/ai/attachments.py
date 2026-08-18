"""
Turns Discord attachments into something the model can read directly.

Images are handed to the model as image parts, text-ish files are inlined into
the message, and anything else is mentioned by name so the model knows it exists
and can reach for a tool (user space, CloudConvert) if it needs the contents.
"""
import logging
from pathlib import Path

import aiohttp

from config import AI_MAX_ATTACHMENT_CHARS, AI_MAX_IMAGES

from .llm import Part

logger = logging.getLogger(__name__)

IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
TEXT_EXTS = {
    'txt', 'md', 'markdown', 'log', 'csv', 'tsv', 'json', 'jsonl', 'yaml', 'yml',
    'toml', 'ini', 'cfg', 'conf', 'env', 'py', 'js', 'ts', 'jsx', 'tsx', 'html',
    'css', 'scss', 'sql', 'sh', 'bash', 'c', 'h', 'cpp', 'java', 'rs', 'go', 'rb',
    'php', 'xml', 'srt', 'vtt', 'diff', 'patch',
}
# Don't download something huge just to throw most of it away.
MAX_DOWNLOAD_BYTES = 2_000_000
FETCH_TIMEOUT = 20


def _ext(filename: str) -> str:
    return Path(filename).suffix.lstrip('.').lower()


async def _fetch_text(url: str) -> tuple[str, str]:
    """Download a text attachment. Returns (text, error)."""
    try:
        timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return "", f"HTTP {resp.status}"
                raw = await resp.content.read(MAX_DOWNLOAD_BYTES + 1)
        if len(raw) > MAX_DOWNLOAD_BYTES:
            return "", "file too large to inline"
        return raw.decode('utf-8', errors='replace'), ""
    except Exception as e:
        return "", str(e)


async def build_attachment_parts(attachments) -> tuple[list, str]:
    """
    Read a message's attachments.

    Returns (image parts, note) — the note is text to append to the user
    message describing inlined files and anything that couldn't be read.
    """
    if not attachments:
        return [], ""

    image_parts = []
    notes = []
    skipped_images = 0

    for att in attachments:
        ext = _ext(att.filename)

        if ext in IMAGE_EXTS:
            if len(image_parts) < AI_MAX_IMAGES:
                image_parts.append(Part.from_image_url(att.url))
            else:
                skipped_images += 1
            continue

        if ext in TEXT_EXTS:
            text, error = await _fetch_text(att.url)
            if error:
                notes.append(f"[System: Attachment `{att.filename}` could not be read: {error}. URL: {att.url}]")
                continue
            if len(text) > AI_MAX_ATTACHMENT_CHARS:
                dropped = len(text) - AI_MAX_ATTACHMENT_CHARS
                text = text[:AI_MAX_ATTACHMENT_CHARS] + f"\n[... truncated, {dropped} more characters]"
            notes.append(f"[System: Attachment `{att.filename}`:\n```\n{text}\n```\n]")
            continue

        notes.append(
            f"[System: Attachment `{att.filename}` ({att.size} bytes) is not text or an image. "
            f"URL: {att.url} — use your tools if you need its contents.]"
        )

    if skipped_images:
        notes.append(f"[System: {skipped_images} further image(s) were not sent to you (limit {AI_MAX_IMAGES}).]")

    if image_parts:
        logger.info(f"Attachments: {len(image_parts)} image(s) sent to the model")

    return image_parts, "\n".join(notes)
