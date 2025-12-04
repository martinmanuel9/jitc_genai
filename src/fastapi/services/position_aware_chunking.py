"""
Position-Aware Document Chunking
Preserves image positions when splitting documents into chunks
"""

import logging
from typing import List, Dict, Any
import json

logger = logging.getLogger("POSITION_AWARE_CHUNKING")


def page_based_chunking_with_positions(
    pages_data: List[Dict[str, Any]],
    document_name: str
) -> List[Dict[str, Any]]:
    """
    Create one chunk per page, preserving image positions.

    Each chunk contains:
    - Full page text
    - All images on that page with complete position metadata
    - Page-level metadata
    """
    chunks = []

    for page_data in pages_data:
        page_num = page_data.get("page", 1)
        page_text = page_data.get("text", "")
        page_images = page_data.get("images", [])

        # Sort images by their character offset or page sequence
        sorted_images = sorted(
            page_images,
            key=lambda img: (img.get("char_offset", 0), img.get("page_sequence", 0))
        )

        # Build image positions metadata (will be stored as JSON in ChromaDB)
        image_positions = []
        for img in sorted_images:
            image_positions.append({
                "filename": img["filename"],
                "storage_path": img["storage_path"],
                "page_number": img["page_number"],
                "page_sequence": img["page_sequence"],
                "bbox": img.get("bbox", [0, 0, 0, 0]),
                "width_pts": img.get("width_pts", 0),
                "height_pts": img.get("height_pts", 0),
                "width_px": img.get("width_px", 0),
                "height_px": img.get("height_px", 0),
                "char_offset": img.get("char_offset", 0),
                "text_before": img.get("text_before", ""),
                "text_after": img.get("text_after", ""),
                "placement_hint": img.get("placement_hint", "inline"),
                "description": img.get("description", "")  # Will be added after vision processing
            })

        chunk = {
            "content": page_text.strip() if page_text else f"Page {page_num}: [no extractable text]",
            "chunk_index": page_num - 1,  # 0-indexed
            "page_number": page_num,
            "section_type": "page",
            "section_title": f"Page {page_num}",
            "has_images": len(sorted_images) > 0,
            "image_count": len(sorted_images),
            "image_positions": image_positions,  # Full position data
            "start_position": 0,
            "end_position": len(page_text) if page_text else 0,
            # Legacy format for backward compatibility
            "images": sorted_images
        }

        chunks.append(chunk)

    logger.info(f"Page-based chunking created {len(chunks)} chunks for {document_name}")
    return chunks


def section_based_chunking_with_positions(
    content: str,
    images_data: List[Dict],
    document_name: str
) -> List[Dict[str, Any]]:
    """
    Create chunks based on document sections, distributing images to appropriate sections.
    """
    import re

    # Detect section boundaries
    sections = []
    lines = content.split('\n')
    current_section = {"title": "Introduction", "content": [], "start_pos": 0}

    for i, line in enumerate(lines):
        line_clean = line.strip()

        # Check for section headers
        is_header = False
        if line_clean and (
            re.match(r'^\d+(\.\d+)*\.?\s+[A-Z]', line_clean) or  # Numbered sections
            (line_clean.isupper() and 5 < len(line_clean) < 80) or  # ALL CAPS
            line_clean.startswith(('APPENDIX', 'CHAPTER', 'SECTION', 'PART'))
        ):
            is_header = True

        if is_header and current_section["content"]:
            # Save previous section
            current_section["end_pos"] = sum(len(l) + 1 for l in current_section["content"])
            sections.append(current_section)
            # Start new section
            current_section = {
                "title": line_clean,
                "content": [],
                "start_pos": sum(len(l) + 1 for l in lines[:i])
            }
        else:
            current_section["content"].append(line)

    # Add last section
    if current_section["content"]:
        current_section["end_pos"] = len(content)
        sections.append(current_section)

    # Assign images to sections based on position
    chunks = []
    for idx, section in enumerate(sections):
        section_text = '\n'.join(section["content"])
        section_start = section["start_pos"]
        section_end = section.get("end_pos", section_start + len(section_text))

        # Find images that belong to this section
        section_images = []
        for img in images_data:
            char_offset = img.get("char_offset", 0)
            if section_start <= char_offset < section_end:
                section_images.append(img)

        # Sort images by position
        section_images.sort(key=lambda img: img.get("char_offset", 0))

        # Build image positions
        image_positions = []
        for img in section_images:
            image_positions.append({
                "filename": img["filename"],
                "storage_path": img["storage_path"],
                "page_number": img.get("page_number", 1),
                "page_sequence": img.get("page_sequence", 0),
                "bbox": img.get("bbox", [0, 0, 0, 0]),
                "char_offset": img.get("char_offset", 0),
                "text_before": img.get("text_before", ""),
                "text_after": img.get("text_after", ""),
                "placement_hint": img.get("placement_hint", "inline"),
                "description": img.get("description", "")
            })

        chunk = {
            "content": section_text.strip(),
            "chunk_index": idx,
            "section_number": idx + 1,
            "section_type": "logical_section",
            "section_title": section["title"],
            "has_images": len(section_images) > 0,
            "image_count": len(section_images),
            "image_positions": image_positions,
            "start_position": section_start,
            "end_position": section_end,
            "images": section_images  # Legacy compatibility
        }

        chunks.append(chunk)

    logger.info(f"Section-based chunking created {len(chunks)} chunks for {document_name}")
    return chunks


def fixed_size_chunking_with_positions(
    content: str,
    images_data: List[Dict],
    chunk_size: int = 1000,
    overlap: int = 200
) -> List[Dict[str, Any]]:
    """
    Create fixed-size chunks while preserving image positions.

    Images are assigned to chunks based on their char_offset.
    """
    chunks = []
    start = 0
    chunk_index = 0

    # Sort images by position
    sorted_images = sorted(images_data, key=lambda img: img.get("char_offset", 0))
    image_idx = 0

    while start < len(content):
        end = min(start + chunk_size, len(content))

        # Adjust to sentence/paragraph boundary
        if end < len(content):
            # Try to break at sentence or paragraph
            last_period = content[start:end].rfind('. ')
            last_newline = content[start:end].rfind('\n\n')

            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:  # Only use if not too early
                end = start + break_point + 1

        chunk_text = content[start:end]

        # Find images in this chunk
        chunk_images = []
        while image_idx < len(sorted_images):
            img = sorted_images[image_idx]
            char_offset = img.get("char_offset", 0)

            if start <= char_offset < end:
                chunk_images.append(img)
                image_idx += 1
            elif char_offset >= end:
                break
            else:
                image_idx += 1

        # Build image positions
        image_positions = []
        for img in chunk_images:
            # Adjust char_offset to be relative to chunk start
            relative_offset = img.get("char_offset", 0) - start

            image_positions.append({
                "filename": img["filename"],
                "storage_path": img["storage_path"],
                "page_number": img.get("page_number", 1),
                "char_offset_absolute": img.get("char_offset", 0),
                "char_offset_relative": relative_offset,
                "text_before": img.get("text_before", ""),
                "text_after": img.get("text_after", ""),
                "placement_hint": img.get("placement_hint", "inline"),
                "description": img.get("description", "")
            })

        chunk = {
            "content": chunk_text.strip(),
            "chunk_index": chunk_index,
            "section_type": "fixed_chunk",
            "section_title": f"Chunk {chunk_index + 1}",
            "has_images": len(chunk_images) > 0,
            "image_count": len(chunk_images),
            "image_positions": image_positions,
            "start_position": start,
            "end_position": end,
            "images": chunk_images  # Legacy compatibility
        }

        chunks.append(chunk)
        chunk_index += 1

        # Move start position with overlap
        start = end - overlap

        if start >= len(content):
            break

    logger.info(f"Fixed-size chunking created {len(chunks)} chunks")
    return chunks


def merge_images_with_descriptions(
    chunks: List[Dict[str, Any]],
    described_images: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Merge vision model descriptions into chunk image positions.

    Args:
        chunks: List of chunks with image_positions
        described_images: Dict mapping image filename to description

    Returns:
        Updated chunks with descriptions in image_positions
    """
    for chunk in chunks:
        if "image_positions" in chunk:
            for img_pos in chunk["image_positions"]:
                filename = img_pos.get("filename", "")
                if filename in described_images:
                    img_pos["description"] = described_images[filename]

        # Also update legacy images field
        if "images" in chunk:
            for img in chunk["images"]:
                filename = img.get("filename", "")
                if filename in described_images:
                    img["description"] = described_images[filename]

    return chunks
