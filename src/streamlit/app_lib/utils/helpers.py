from io import BytesIO
from typing import Any


def create_file_like_object(content: str, filename: str) -> BytesIO:
    # Encode content as bytes
    content_bytes = content.encode('utf-8')

    # Create BytesIO object
    file_obj = BytesIO(content_bytes)
    file_obj.name = filename

    return file_obj
