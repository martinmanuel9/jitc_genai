"""
Image Extraction Service
Extracts images, diagrams, and visual content from PDFs.

Capabilities:
- XObject image extraction (standard PDF images)
- Inline image block detection
- Vector drawing detection
- Visual probing (non-text visual content detection)
- Page rasterization for complex content
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import PyMuPDF
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.warning("PyMuPDF not available - image extraction will be disabled")

# Try to import PIL for image processing
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("PIL/Pillow not available - image processing limited")

# Try to import numpy for visual probing
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("NumPy not available - visual probing disabled")


@dataclass
class ExtractedImage:
    """Metadata for an extracted image"""
    image_path: str
    page_number: int
    image_type: str  # "xobject", "inline", "drawing", "raster"
    width: Optional[int] = None
    height: Optional[int] = None
    xref: Optional[int] = None  # XObject reference number


class ImageExtractionService:
    """
    Service for extracting visual content from PDF documents.

    Detection Methods:
    1. XObject Images - Standard embedded images
    2. Inline Image Blocks - Images embedded in content stream
    3. Vector Drawings - Diagrams, charts, schematics
    4. Visual Probing - Pixel-level non-text content detection

    Based on notebook's comprehensive image detection approach.
    """

    def __init__(
        self,
        image_output_dir: str = "extracted_images",
        detect_inline_blocks: bool = True,
        detect_drawings: bool = True,
        min_drawing_area: float = 2000.0,  # pixels²
        probe_dpi: int = 72,  # DPI for visual probing
        probe_threshold: float = 0.01,  # 1% non-white pixels
        raster_dpi: int = 144  # DPI for page rasterization
    ):
        """
        Initialize image extraction service.

        Args:
            image_output_dir: Directory to save extracted images
            detect_inline_blocks: Enable inline image block detection
            detect_drawings: Enable vector drawing detection
            min_drawing_area: Minimum area (px²) to consider a drawing significant
            probe_dpi: DPI for visual probing pixmap
            probe_threshold: Minimum non-white pixel ratio to trigger rasterization
            raster_dpi: DPI for full page rasterization
        """
        if not HAS_PYMUPDF:
            raise ImportError(
                "PyMuPDF (fitz) is required for image extraction. "
                "Install with: pip install pymupdf"
            )

        self.image_output_dir = Path(image_output_dir)
        self.detect_inline_blocks = detect_inline_blocks
        self.detect_drawings = detect_drawings
        self.min_drawing_area = min_drawing_area
        self.probe_dpi = probe_dpi
        self.probe_threshold = probe_threshold
        self.raster_dpi = raster_dpi

        logger.info(
            f"ImageExtractionService initialized with "
            f"inline_blocks={detect_inline_blocks}, "
            f"drawings={detect_drawings}, "
            f"probe_threshold={probe_threshold}"
        )

    def extract_images_from_pdf(
        self,
        pdf_path: str,
        document_id: str
    ) -> Dict[int, List[ExtractedImage]]:
        """
        Extract all images from PDF document.

        Args:
            pdf_path: Path to PDF file
            document_id: Unique identifier for this document

        Returns:
            Dictionary mapping page_number -> list of ExtractedImage objects

        Example:
            {
                1: [ExtractedImage(path="img1.png", page_number=1, image_type="xobject")],
                3: [ExtractedImage(path="img2.png", page_number=3, image_type="raster")]
            }
        """
        logger.info(f"Extracting images from PDF: {pdf_path}")
        logger.info(f"Document ID: {document_id}")

        # Create output directory
        output_dir = self.image_output_dir / document_id
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {output_dir}")

        page_images = {}
        total_images = 0

        try:
            doc = fitz.open(pdf_path)
            base_name = Path(pdf_path).stem

            logger.info(f"Processing {len(doc)} pages...")

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_idx = page_num + 1  # 1-indexed for user-facing numbers
                images = []

                # Method 1: Extract XObject images (most common)
                xobject_images = self._extract_xobject_images(
                    doc, page, page_idx, base_name, output_dir
                )
                images.extend(xobject_images)

                # Method 2-4: If no XObjects found, check for other visual content
                if not xobject_images:
                    # Check for inline image blocks
                    has_inline = False
                    if self.detect_inline_blocks and self._has_inline_images(page):
                        logger.info(f"Page {page_idx}: Detected inline image blocks")
                        has_inline = True

                    # Check for vector drawings
                    has_drawings = False
                    if self.detect_drawings and self._has_drawings(page):
                        logger.info(f"Page {page_idx}: Detected vector drawings")
                        has_drawings = True

                    # Visual probe for any non-text content
                    has_visual_content = False
                    if HAS_NUMPY and self._visual_probe_has_content(page):
                        logger.info(f"Page {page_idx}: Visual probe detected non-text content")
                        has_visual_content = True

                    # If any visual content detected, rasterize the page
                    if has_inline or has_drawings or has_visual_content:
                        raster_image = self._rasterize_page(
                            page, page_idx, base_name, output_dir
                        )
                        if raster_image:
                            images.append(raster_image)
                            logger.info(f"Page {page_idx}: Rasterized to capture visual content")

                # Store images for this page
                if images:
                    page_images[page_idx] = images
                    total_images += len(images)
                    logger.info(f"Page {page_idx}: Extracted {len(images)} image(s)")

            doc.close()

            logger.info(
                f"Extraction complete: {total_images} images from "
                f"{len(page_images)} pages (out of {len(doc)} total pages)"
            )
            return page_images

        except Exception as e:
            logger.error(f"Image extraction failed for {pdf_path}: {e}", exc_info=True)
            return {}

    def _extract_xobject_images(
        self,
        doc: 'fitz.Document',
        page: 'fitz.Page',
        page_idx: int,
        base_name: str,
        output_dir: Path
    ) -> List[ExtractedImage]:
        """
        Extract XObject images from page.
        XObjects are the standard way images are embedded in PDFs.

        Args:
            doc: PyMuPDF document
            page: PyMuPDF page
            page_idx: Page number (1-indexed)
            base_name: Base filename for saved images
            output_dir: Directory to save images

        Returns:
            List of extracted image metadata
        """
        images = []

        try:
            page_images = page.get_images(full=True)
            logger.debug(f"Page {page_idx}: Found {len(page_images)} XObject image(s)")

            for img_idx, img in enumerate(page_images):
                xref = img[0]

                try:
                    # Extract image bytes
                    info = doc.extract_image(xref)
                    ext = info.get("ext", "png")
                    width = info.get("width")
                    height = info.get("height")

                    # Create output filename
                    out_path = output_dir / f"{base_name}_p{page_idx}_img{img_idx}_xref{xref}.{ext}"

                    # Save image
                    with open(out_path, "wb") as f:
                        f.write(info["image"])

                    # Normalize PNG mode if PIL available
                    if ext.lower() == "png" and HAS_PIL:
                        try:
                            with Image.open(out_path) as im:
                                # Convert to RGB or grayscale for better compatibility
                                if im.mode not in ("L", "RGB", "RGBA"):
                                    im = im.convert("RGB")
                                    im.save(out_path)
                        except Exception as e:
                            logger.warning(f"PNG normalization failed for xref {xref}: {e}")

                    images.append(ExtractedImage(
                        image_path=str(out_path),
                        page_number=page_idx,
                        image_type="xobject",
                        width=width,
                        height=height,
                        xref=xref
                    ))

                    logger.debug(
                        f"Extracted XObject: page={page_idx}, xref={xref}, "
                        f"size={width}x{height}, format={ext}"
                    )

                except Exception as e:
                    logger.warning(f"Failed to extract xref {xref} on page {page_idx}: {e}")

        except Exception as e:
            logger.warning(f"Failed to get XObject images for page {page_idx}: {e}")

        return images

    def _has_inline_images(self, page: 'fitz.Page') -> bool:
        """
        Check if page contains inline image blocks.
        Inline images are embedded directly in the content stream.

        Args:
            page: PyMuPDF page

        Returns:
            True if inline images detected
        """
        try:
            raw = page.get_text("rawdict") or {}
            blocks = raw.get("blocks", []) if isinstance(raw, dict) else []

            for block in blocks:
                if block.get("type") == 1:  # type=1 indicates image block
                    return True

        except Exception as e:
            logger.debug(f"Inline image detection failed: {e}")

        return False

    def _has_drawings(self, page: 'fitz.Page') -> bool:
        """
        Check if page contains significant vector drawings.
        Identifies diagrams, charts, schematics rendered as vector paths.

        Args:
            page: PyMuPDF page

        Returns:
            True if significant drawings detected
        """
        try:
            drawings = page.get_drawings() or []

            for drawing in drawings:
                rect = drawing.get("rect")
                if isinstance(rect, fitz.Rect):
                    # Calculate drawing area
                    area = max(0.0, (rect.x1 - rect.x0) * (rect.y1 - rect.y0))

                    if area >= self.min_drawing_area:
                        logger.debug(
                            f"Detected significant drawing: area={area:.0f}px², "
                            f"threshold={self.min_drawing_area}px²"
                        )
                        return True

        except Exception as e:
            logger.debug(f"Drawing detection failed: {e}")

        return False

    def _visual_probe_has_content(self, page: 'fitz.Page') -> bool:
        """
        Visual probe: render page and check for non-text pixels.
        This catches visual content not detected by other methods.

        Method:
        1. Render page at low DPI
        2. Mask out text regions
        3. Check remaining pixels for non-white content
        4. If >threshold non-white, consider it visual content

        Args:
            page: PyMuPDF page

        Returns:
            True if non-text visual content detected
        """
        if not HAS_NUMPY:
            return False

        try:
            # Get text block rectangles to mask
            text_rects = []
            for block in page.get_text("blocks") or []:
                # Text blocks: (x0, y0, x1, y1, text, block_no, block_type, ...)
                if len(block) >= 8 and block[6] == 0:  # block_type=0 is text
                    text_rects.append(fitz.Rect(block[0], block[1], block[2], block[3]))

            # Render page at probe resolution
            scale = self.probe_dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            w, h = pix.width, pix.height
            if w == 0 or h == 0:
                return False

            # Convert pixmap to numpy array
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, w, pix.n)

            # Mask text regions (set to white)
            for rect in text_rects:
                x0 = max(0, int(rect.x0 * scale))
                y0 = max(0, int(rect.y0 * scale))
                x1 = min(w, int(rect.x1 * scale))
                y1 = min(h, int(rect.y1 * scale))

                if x1 > x0 and y1 > y0:
                    img[y0:y1, x0:x1, :] = 255  # white out text regions

            # Count non-white pixels
            nonwhite_pixels = np.any(img < 250, axis=2)  # <250 to catch near-white
            nonwhite_ratio = nonwhite_pixels.sum() / (w * h)

            logger.debug(
                f"Visual probe: {nonwhite_ratio*100:.2f}% non-white pixels "
                f"(threshold: {self.probe_threshold*100:.2f}%)"
            )

            return nonwhite_ratio >= self.probe_threshold

        except Exception as e:
            logger.debug(f"Visual probe failed: {e}")
            return False

    def _rasterize_page(
        self,
        page: 'fitz.Page',
        page_idx: int,
        base_name: str,
        output_dir: Path
    ) -> Optional[ExtractedImage]:
        """
        Rasterize entire page to PNG.
        Used when other methods detect visual content but can't extract it cleanly.

        Args:
            page: PyMuPDF page
            page_idx: Page number (1-indexed)
            base_name: Base filename
            output_dir: Output directory

        Returns:
            ExtractedImage metadata or None if rasterization fails
        """
        try:
            # Render at higher DPI for quality
            scale = self.raster_dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)

            # Save as PNG
            out_path = output_dir / f"{base_name}_p{page_idx}_raster.png"
            pix.save(str(out_path))

            logger.debug(
                f"Rasterized page {page_idx}: {pix.width}x{pix.height} pixels "
                f"at {self.raster_dpi} DPI"
            )

            return ExtractedImage(
                image_path=str(out_path),
                page_number=page_idx,
                image_type="raster",
                width=pix.width,
                height=pix.height
            )

        except Exception as e:
            logger.error(f"Page rasterization failed for page {page_idx}: {e}")
            return None

    def get_extraction_stats(
        self,
        page_images: Dict[int, List[ExtractedImage]]
    ) -> Dict[str, Any]:
        """
        Generate statistics about extracted images.

        Args:
            page_images: Result from extract_images_from_pdf()

        Returns:
            Statistics dictionary
        """
        total_images = sum(len(images) for images in page_images.values())

        type_counts = {
            "xobject": 0,
            "inline": 0,
            "drawing": 0,
            "raster": 0
        }

        for images in page_images.values():
            for img in images:
                type_counts[img.image_type] = type_counts.get(img.image_type, 0) + 1

        return {
            "total_images": total_images,
            "pages_with_images": len(page_images),
            "images_by_type": type_counts,
            "average_images_per_page": total_images / len(page_images) if page_images else 0
        }
