from typing import List


def paginate_text(text: str, max_length: int = 4000) -> List[str]:
    """Split text into pages that fit within Discord embed description limits."""
    if len(text) <= max_length:
        return [text]

    pages = []
    lines = text.split('\n')
    current_page = ""
    current_length = 0

    for line in lines:
        line_length = len(line) + 1  # +1 for newline
        if line_length > max_length:
            if current_page:
                page = current_page.rstrip()
                if page:
                    pages.append(page)
                current_page = ""
                current_length = 0
            chunks = []
            remaining = line
            while len(remaining) > max_length:
                chunk = remaining[:max_length]
                last_space = chunk.rfind(' ')
                if last_space > max_length // 2:  # Only break at space if it's not too early
                    chunk = chunk[:last_space]
                chunks.append(chunk)
                remaining = remaining[len(chunk):].lstrip()  # Remove leading spaces
            
            if remaining:
                chunks.append(remaining)
            for chunk in chunks[:-1]:  # All but last chunk
                pages.append(chunk)
            current_page = chunks[-1] + '\n'
            current_length = len(current_page)
            continue

        if current_length + line_length > max_length and current_page:
            page = current_page.rstrip()
            if page:
                pages.append(page)
            current_page = line + '\n'
            current_length = line_length
        else:
            current_page += line + '\n'
            current_length += line_length

    if current_page:
        page = current_page.rstrip()
        if page:
            pages.append(page)

    return pages