from typing import Optional


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return ''.join(c for c in text if c == '\n' or c == '\t' or (32 <= ord(c) <= 126))
