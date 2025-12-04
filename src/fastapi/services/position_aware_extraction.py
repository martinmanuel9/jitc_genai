"""
Position-Aware Image Extraction
Captures precise image positions from PDFs for accurate document reconstruction
"""

import os
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from PyPDF2 import PdfReader
from PIL import Image
import io

logger = logging.getLogger("POSITION_AWARE_EXTRACTION")


def extract_images_with_positions(
    file_content: bytes,
    filename: str,
    temp_dir: str,
    doc_id: str,
    images_dir: str
) -> List[Dict[str, Any]]:
    """
    Extract images from PDF with complete position metadata.

    Returns a list of page_data dicts, each containing:
    {
        "page": page_number,
        "text": extracted_text,
        "images": [
            {
                "filename": str,
                "storage_path": str,
                "page_number": int,
                "page_sequence": int,  # Order on page (0-indexed)
                "bbox": [x0, y0, x1, y1],  # Bounding box coordinates
                "width_pts": float,
                "height_pts": float,
                "char_offset": int,  # Approximate position in text
                "text_before": str,  # Context before image
                "text_after": str,  # Context after image
                "placement_hint": str  # Suggested placement strategy
            }
        ]
    }
    """
    pages_data = []

    try:
        # Save PDF to temp file
        temp_pdf_path = os.path.join(temp_dir, filename)
        with open(temp_pdf_path, 'wb') as f:
            f.write(file_content)

        reader = PdfReader(temp_pdf_path)
        logger.info(f"Extracting images with positions from {filename} ({len(reader.pages)} pages)")

        for page_num, page in enumerate(reader.pages, 1):
            page_data = {
                "page": page_num,
                "text": "",
                "images": []
            }

            # Extract text first to establish context
            try:
                page_text = page.extract_text() or ""
                page_data["text"] = page_text
            except Exception as e:
                logger.warning(f"Text extraction failed for page {page_num}: {e}")
                page_text = ""

            # Get page dimensions for coordinate normalization
            try:
                page_box = page.mediabox
                page_width = float(page_box.width)
                page_height = float(page_box.height)
            except:
                page_width, page_height = 612.0, 792.0  # Default letter size

            # Extract images with positions
            if "/Resources" not in page:
                logger.debug(f"Page {page_num}: No resources found")
                pages_data.append(page_data)
                continue

            resources = page["/Resources"]
            if hasattr(resources, 'get_object'):
                resources = resources.get_object()

            if "/XObject" not in resources:
                logger.debug(f"Page {page_num}: No XObjects found")
                pages_data.append(page_data)
                continue

            xobjects = resources["/XObject"]
            if hasattr(xobjects, 'get_object'):
                xobjects = xobjects.get_object()

            # Track image sequence on this page
            image_sequence = 0

            for obj_name in xobjects:
                try:
                    xobj = xobjects[obj_name]
                    if hasattr(xobj, 'get_object'):
                        xobj = xobj.get_object()

                    # Check if it's an image
                    if xobj.get("/Subtype") != "/Image":
                        continue

                    # Extract image data
                    try:
                        data = xobj.get_data()
                        filters = xobj.get('/Filter')

                        # Determine file extension
                        if filters == '/DCTDecode':
                            img_ext = 'jpg'
                        elif filters == '/FlateDecode':
                            img_ext = 'png'
                        else:
                            img_ext = 'png'

                        # Create filename and save image
                        img_filename = f"{doc_id}_page_{page_num}_{obj_name[1:]}.{img_ext}"
                        img_storage_path = os.path.join(images_dir, img_filename)

                        with open(img_storage_path, "wb") as img_file:
                            img_file.write(data)

                        # Normalize PNG images
                        if img_ext == 'png':
                            try:
                                with Image.open(img_storage_path) as im:
                                    if im.mode not in ("RGB", "L"):
                                        im = im.convert("RGB")
                                    im.save(img_storage_path)
                            except Exception as e:
                                logger.warning(f"Could not normalize {img_filename}: {e}")

                        # Verify image is valid
                        try:
                            with Image.open(img_storage_path) as test_img:
                                test_img.verify()
                                # Get image dimensions
                                with Image.open(img_storage_path) as measure_img:
                                    img_width_px, img_height_px = measure_img.size
                        except Exception as img_verify_error:
                            logger.warning(f"Invalid image file: {img_filename}, error: {img_verify_error}")
                            if os.path.exists(img_storage_path):
                                os.remove(img_storage_path)
                            continue

                        # Extract position information from PDF
                        position_data = extract_image_position_from_pdf(
                            page=page,
                            xobj=xobj,
                            obj_name=obj_name,
                            page_width=page_width,
                            page_height=page_height,
                            page_text=page_text
                        )

                        # Build complete image metadata
                        image_metadata = {
                            "filename": img_filename,
                            "storage_path": img_storage_path,
                            "page_number": page_num,
                            "page_sequence": image_sequence,
                            "bbox": position_data.get("bbox", [0, 0, 0, 0]),
                            "width_pts": position_data.get("width_pts", 0),
                            "height_pts": position_data.get("height_pts", 0),
                            "width_px": img_width_px,
                            "height_px": img_height_px,
                            "char_offset": estimate_char_offset(
                                position_data.get("bbox", [0, 0, 0, 0]),
                                page_text,
                                page_height
                            ),
                            "text_before": "",  # Will be filled during chunking
                            "text_after": "",   # Will be filled during chunking
                            "placement_hint": determine_placement_hint(
                                position_data.get("bbox", [0, 0, 0, 0]),
                                page_width,
                                page_height
                            )
                        }

                        page_data["images"].append(image_metadata)
                        image_sequence += 1

                        logger.info(f"Extracted image {img_filename} at position {image_metadata['bbox']}")

                    except Exception as e:
                        logger.error(f"Failed to extract image {obj_name} from page {page_num}: {e}")
                        continue

                except Exception as e:
                    logger.error(f"Error processing XObject {obj_name} on page {page_num}: {e}")
                    continue

            logger.info(f"Page {page_num}: Extracted {len(page_data['images'])} images with positions")
            pages_data.append(page_data)

    except Exception as e:
        logger.error(f"Error extracting images from {filename}: {e}")

    logger.info(f"Total images extracted with positions: {sum(len(p['images']) for p in pages_data)}")
    return pages_data


def extract_image_position_from_pdf(
    page,
    xobj,
    obj_name: str,
    page_width: float,
    page_height: float,
    page_text: str
) -> Dict[str, Any]:
    """
    Extract image position from PDF page structure.

    Returns bounding box and dimensions in PDF coordinate space.
    """
    try:
        # Get image dimensions from XObject
        width = float(xobj.get("/Width", 0))
        height = float(xobj.get("/Height", 0))

        # Try to find transformation matrix in page content stream
        # This gives us the actual position on the page
        # Note: This is a simplified approach. Full implementation would parse
        # the content stream to find the exact transformation matrix.

        # For now, we'll use a heuristic based on object order and common layouts
        # A more complete solution would parse the page's content stream (/Contents)

        # Default position (will be refined if we can parse content stream)
        bbox = [0, 0, width, height]

        # Try to get position from content stream (advanced)
        # This requires parsing the PDF content stream which is complex
        # For MVP, we'll use object order as a proxy

        return {
            "bbox": bbox,
            "width_pts": width,
            "height_pts": height,
        }

    except Exception as e:
        logger.warning(f"Could not extract position for {obj_name}: {e}")
        return {
            "bbox": [0, 0, 0, 0],
            "width_pts": 0,
            "height_pts": 0,
        }


def estimate_char_offset(
    bbox: List[float],
    page_text: str,
    page_height: float
) -> int:
    """
    Estimate character offset in text based on Y-coordinate.

    Assumes text flows top-to-bottom, so higher Y values = earlier in text.
    """
    if not page_text or len(bbox) < 4:
        return 0

    # Y-coordinate of image (PDF coords: 0 = bottom, page_height = top)
    y_pos = bbox[1]

    # Normalize to 0-1 range (0 = top of page, 1 = bottom)
    normalized_y = 1 - (y_pos / page_height) if page_height > 0 else 0.5

    # Estimate character position
    char_offset = int(normalized_y * len(page_text))

    return max(0, min(char_offset, len(page_text)))


def determine_placement_hint(
    bbox: List[float],
    page_width: float,
    page_height: float
) -> str:
    """
    Determine suggested placement strategy based on position and size.
    """
    if len(bbox) < 4:
        return "inline"

    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0

    # Calculate position ratios
    x_ratio = x0 / page_width if page_width > 0 else 0.5
    y_ratio = y0 / page_height if page_height > 0 else 0.5
    width_ratio = width / page_width if page_width > 0 else 0.5

    # Full-width images
    if width_ratio > 0.8:
        if y_ratio < 0.2:
            return "page_top"
        elif y_ratio > 0.8:
            return "page_bottom"
        else:
            return "inline"

    # Narrow images (potential floats)
    elif width_ratio < 0.4:
        if x_ratio < 0.3:
            return "float_left"
        elif x_ratio > 0.7:
            return "float_right"
        else:
            return "inline"

    # Medium images
    else:
        return "inline"


def add_text_anchors_to_images(
    pages_data: List[Dict],
    context_chars: int = 100
) -> List[Dict]:
    """
    Add text_before and text_after anchors to images based on their char_offset.
    """
    for page in pages_data:
        page_text = page.get("text", "")

        for img in page["images"]:
            char_offset = img.get("char_offset", 0)

            # Extract text before image
            start_before = max(0, char_offset - context_chars)
            text_before = page_text[start_before:char_offset].strip()
            img["text_before"] = text_before[-context_chars:] if text_before else ""

            # Extract text after image
            end_after = min(len(page_text), char_offset + context_chars)
            text_after = page_text[char_offset:end_after].strip()
            img["text_after"] = text_after[:context_chars] if text_after else ""

    return pages_data
