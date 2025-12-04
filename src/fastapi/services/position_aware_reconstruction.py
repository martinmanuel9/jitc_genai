"""
Position-Aware Document Reconstruction
Reconstructs documents with images placed at their correct original positions
"""

import logging
import json
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("POSITION_AWARE_RECONSTRUCTION")


def reconstruct_document_with_positions(
    chunks_data: List[Dict[str, Any]],
    base_image_url: str = "/api/vectordb/images"
) -> Tuple[str, List[Dict], Dict]:
    """
    Reconstruct document with images at their correct positions.

    Args:
        chunks_data: List of chunks with metadata
        base_image_url: Base URL for image links

    Returns:
        Tuple of (reconstructed_markdown, images_list, metadata_dict)
    """
    # Sort chunks by page/chunk index
    sorted_chunks = sorted(
        chunks_data,
        key=lambda x: (
            x.get("metadata", {}).get("page_number", 999),
            x.get("metadata", {}).get("chunk_index", 0)
        )
    )

    lines = []
    all_images = []
    metadata = {
        "total_chunks": len(sorted_chunks),
        "total_images": 0,
        "pages": set(),
        "vision_models_used": set(),
        "ocr_used": False
    }

    # Document header
    if sorted_chunks:
        doc_name = sorted_chunks[0].get("metadata", {}).get("document_name", "Untitled")
        lines.append(f"# {doc_name}\n")

    last_section_title = None
    last_page_number = None

    for chunk in sorted_chunks:
        md = chunk.get("metadata", {})
        content = chunk.get("content", "")

        # Extract chunk metadata
        section_title = md.get("section_title", "")
        section_type = md.get("section_type", "")
        page_number = md.get("page_number")

        # Update document metadata
        if page_number:
            metadata["pages"].add(page_number)
        if md.get("ocr_used"):
            metadata["ocr_used"] = True

        # Add section headers
        if section_title and section_title != last_section_title:
            if section_type == "page":
                lines.append(f"\n---\n**{section_title}**\n")
            else:
                lines.append(f"\n## {section_title}\n")
            last_section_title = section_title
        elif page_number and page_number != last_page_number:
            lines.append(f"\n---\n**Page {page_number}**\n")
            last_page_number = page_number

        # Parse image positions from metadata
        image_positions_json = md.get("image_positions", "[]")
        try:
            if isinstance(image_positions_json, str):
                image_positions = json.loads(image_positions_json)
            elif isinstance(image_positions_json, list):
                image_positions = image_positions_json
            else:
                image_positions = []
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse image_positions for chunk {md.get('chunk_index', '?')}")
            image_positions = []

        # If no image_positions, try legacy format
        if not image_positions:
            image_positions = extract_images_from_legacy_metadata(md)
            if image_positions:
                logger.info(f"Chunk {md.get('chunk_index', '?')}: Using legacy format, found {len(image_positions)} images")
        else:
            logger.info(f"Chunk {md.get('chunk_index', '?')}: Found {len(image_positions)} images in position-aware format")

        # Reconstruct content with images at correct positions
        if image_positions:
            reconstructed_content = insert_images_at_positions(
                content=content,
                image_positions=image_positions,
                base_image_url=base_image_url,
                all_images=all_images,
                metadata=metadata
            )
            lines.append(reconstructed_content)
        else:
            lines.append(content)

        lines.append("")  # Spacing between chunks

    # Finalize metadata
    metadata["total_images"] = len(all_images)
    metadata["pages"] = sorted(list(metadata["pages"]))
    metadata["vision_models_used"] = sorted(list(metadata["vision_models_used"]))

    reconstructed_markdown = "\n".join(lines).strip()

    return reconstructed_markdown, all_images, metadata


def insert_images_at_positions(
    content: str,
    image_positions: List[Dict],
    base_image_url: str,
    all_images: List[Dict],
    metadata: Dict
) -> str:
    """
    Insert images into content at their correct positions.

    Uses multiple strategies:
    1. char_offset - exact character position
    2. text_anchor - find matching text
    3. placement_hint - use positioning strategy
    """
    # Sort images by their position
    sorted_images = sorted(
        image_positions,
        key=lambda img: (
            img.get("char_offset", img.get("char_offset_relative", 0)),
            img.get("page_sequence", 0)
        )
    )

    # Build list of (position, image_markdown) tuples
    insertions = []

    for img_pos in sorted_images:
        # Log image position details for debugging
        logger.info(f"Processing image: {img_pos.get('filename', 'unknown')}, "
                   f"has description: {bool(img_pos.get('description', ''))}, "
                   f"char_offset: {img_pos.get('char_offset', 'N/A')}")

        # Generate image markdown
        img_markdown = generate_image_markdown(img_pos, base_image_url, len(all_images) + 1)
        logger.info(f"Generated markdown length: {len(img_markdown)} chars")

        # Determine insertion position
        position = determine_insertion_position(img_pos, content)

        insertions.append((position, img_markdown, img_pos))

        # Track image (include storage_path for compatibility)
        all_images.append({
            "filename": img_pos.get("filename", ""),
            "storage_path": img_pos.get("storage_path", ""),
            "description": img_pos.get("description", ""),
            "page_number": img_pos.get("page_number"),
            "position": img_pos.get("char_offset", 0),
            "exists": True  # Assume exists if in metadata
        })

        # Track vision models
        desc = img_pos.get("description", "")
        if "openai" in desc.lower():
            metadata["vision_models_used"].add("openai")
        if "huggingface" in desc.lower():
            metadata["vision_models_used"].add("huggingface")

    # Insert images in reverse order (to preserve positions)
    insertions.sort(key=lambda x: x[0], reverse=True)
    logger.info(f"Inserting {len(insertions)} images into content (length: {len(content)} chars)")

    result = content
    for position, img_markdown, img_pos in insertions:
        # Insert image at position
        placement_hint = img_pos.get("placement_hint", "inline")

        if placement_hint == "float_right":
            img_markdown = f'<div style="float: right; margin: 10px;">\n{img_markdown}\n</div>\n'
        elif placement_hint == "float_left":
            img_markdown = f'<div style="float: left; margin: 10px;">\n{img_markdown}\n</div>\n'

        result = result[:position] + "\n" + img_markdown + "\n" + result[position:]
        logger.debug(f"Inserted image at position {position}, result now {len(result)} chars")

    logger.info(f"After inserting images: content length changed from {len(content)} to {len(result)} chars")
    return result


def determine_insertion_position(img_pos: Dict, content: str) -> int:
    """
    Determine where to insert an image in the content.

    Priority:
    1. char_offset_relative - exact position in chunk
    2. text_anchor_before/after - find matching text
    3. Default to end of content
    """
    # Try relative character offset
    char_offset = img_pos.get("char_offset_relative")
    if char_offset is not None and 0 <= char_offset <= len(content):
        return char_offset

    # Try absolute offset (for page-based chunks)
    char_offset = img_pos.get("char_offset")
    if char_offset is not None and 0 <= char_offset <= len(content):
        return char_offset

    # Try text anchors
    text_before = img_pos.get("text_before", "").strip()
    text_after = img_pos.get("text_after", "").strip()

    if text_before:
        # Find where text_before appears
        idx = content.find(text_before)
        if idx != -1:
            return idx + len(text_before)

    if text_after:
        # Find where text_after appears
        idx = content.find(text_after)
        if idx != -1:
            return idx

    # Default: place at end of content
    return len(content)


def generate_image_markdown(
    img_pos: Dict,
    base_image_url: str,
    image_number: int
) -> str:
    """
    Generate markdown for an image with caption.
    """
    filename = img_pos.get("filename", "image.png")
    description = img_pos.get("description", "")

    # Clean description (remove model prefixes)
    clean_desc = description
    for prefix in ["OpenAI Vision:", "HuggingFace BLIP:", "Enhanced analysis:", "Basic analysis:"]:
        if clean_desc.startswith(prefix):
            clean_desc = clean_desc[len(prefix):].strip()

    # Build image URL
    image_url = f"{base_image_url}/{filename}"

    # Generate markdown
    alt_text = f"Image {image_number}" + (f": {clean_desc[:50]}" if clean_desc else "")
    markdown = f"![{alt_text}]({image_url})"

    # Add caption if description exists
    if clean_desc:
        caption = clean_desc if len(clean_desc) <= 200 else clean_desc[:197] + "..."
        markdown += f"\n*{caption}*"

    return markdown


def extract_images_from_legacy_metadata(md: Dict) -> List[Dict]:
    """
    Extract image positions from legacy metadata format (for backward compatibility).
    """
    images = []

    # Try to parse legacy JSON fields
    try:
        filenames = json.loads(md.get("image_filenames", "[]"))
        paths = json.loads(md.get("image_storage_paths", "[]"))
        descs = json.loads(md.get("image_descriptions", "[]"))

        for i, (filename, path) in enumerate(zip(filenames, paths)):
            images.append({
                "filename": filename,
                "storage_path": path,
                "description": descs[i] if i < len(descs) else "",
                "page_number": md.get("page_number", 1),
                "page_sequence": i,
                "char_offset": None,  # Unknown in legacy format
                "placement_hint": "inline"
            })
    except (json.JSONDecodeError, KeyError) as e:
        logger.debug(f"Could not extract legacy images: {e}")

    return images


def format_for_word_export(
    reconstructed_content: str,
    images: List[Dict],
    metadata: Dict
) -> Dict:
    """
    Format reconstructed document for Word export.

    Returns structured data that can be used by word_export_service.
    """
    return {
        "content": reconstructed_content,
        "images": images,
        "metadata": {
            **metadata,
            "format_type": "markdown_with_positions"
        },
        "sections": parse_sections_from_markdown(reconstructed_content)
    }


def parse_sections_from_markdown(content: str) -> List[Dict]:
    """
    Parse sections from markdown content for structured export.
    """
    sections = []
    current_section = {"level": 0, "title": "", "content": []}

    for line in content.split('\n'):
        if line.startswith('#'):
            # Save previous section
            if current_section["content"]:
                sections.append(current_section)

            # Start new section
            level = len(line) - len(line.lstrip('#'))
            title = line.lstrip('#').strip()
            current_section = {
                "level": level,
                "title": title,
                "content": []
            }
        else:
            current_section["content"].append(line)

    # Add last section
    if current_section["content"]:
        sections.append(current_section)

    return sections
