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

        if current_length + line_length > max_length and current_page:
            pages.append(current_page.rstrip())
            current_page = line + '\n'
            current_length = line_length
        else:
            current_page += line + '\n'
            current_length += line_length

    if current_page:
        pages.append(current_page.rstrip())

    return pages