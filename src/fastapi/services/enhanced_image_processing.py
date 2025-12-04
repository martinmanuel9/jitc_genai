"""
Enhanced Image Processing Pipeline
Integrates ImageExtractionService and ImageDescriptionService with document ingestion.
Provides a unified interface for image understanding during document processing.

This is an enhancement layer that can be enabled via feature flag to replace
or augment the existing image processing in document_ingestion_service.py
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Import our new services
from .image_extraction_service import ImageExtractionService, ExtractedImage
from .image_description_service import ImageDescriptionService, ImageDescription


@dataclass
class ProcessedImage:
    """
    Unified format for processed images with descriptions.
    Compatible with existing ChromaDB metadata format.
    """
    image_path: str
    page_number: int
    description: str
    image_type: str  # "xobject", "inline", "drawing", "raster"
    model_used: str
    storage_path: str  # Relative path for ChromaDB storage
    width: Optional[int] = None
    height: Optional[int] = None
    confidence: Optional[str] = None


class EnhancedImageProcessingPipeline:
    """
    Unified image processing pipeline combining extraction and description.

    Features:
    - PyMuPDF-based extraction (XObject, inline, drawings)
    - MarkItDown multimodal descriptions
    - Compatible with existing ChromaDB schema
    - Parallel processing
    - Comprehensive error handling

    Usage:
        pipeline = EnhancedImageProcessingPipeline()
        processed_images = pipeline.process_document(
            pdf_path="/path/to/doc.pdf",
            document_id="doc_123",
            context="MIL-STD-188 specification"
        )
    """

    def __init__(
        self,
        image_output_dir: str = "extracted_images",
        llm_model: str = "gpt-4o",
        max_extraction_workers: int = 1,  # Sequential for PyMuPDF (not thread-safe)
        max_description_workers: int = 4,  # Parallel for API calls
        enable_visual_probing: bool = True,
        enable_drawing_detection: bool = True,
        api_key: Optional[str] = None
    ):
        """
        Initialize enhanced image processing pipeline.

        Args:
            image_output_dir: Directory for extracted images
            llm_model: Multimodal model for descriptions
            max_extraction_workers: Extraction parallelism (keep at 1 for PyMuPDF)
            max_description_workers: Description parallelism
            enable_visual_probing: Enable pixel-level content detection
            enable_drawing_detection: Enable vector drawing detection
            api_key: OpenAI API key (uses env var if not provided)
        """
        logger.info("Initializing EnhancedImageProcessingPipeline")

        # Initialize extraction service
        try:
            self.extraction_service = ImageExtractionService(
                image_output_dir=image_output_dir,
                detect_inline_blocks=True,
                detect_drawings=enable_drawing_detection,
                probe_threshold=0.01 if enable_visual_probing else 1.0  # Disable probe if threshold too high
            )
            logger.info(" Image extraction service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize extraction service: {e}")
            raise

        # Initialize description service
        try:
            self.description_service = ImageDescriptionService(
                llm_model=llm_model,
                max_workers=max_description_workers,
                api_key=api_key
            )
            logger.info(" Image description service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize description service: {e}")
            raise

        self.image_output_dir = Path(image_output_dir)

    def process_document(
        self,
        pdf_path: str,
        document_id: str,
        context: Optional[str] = None
    ) -> Dict[int, List[ProcessedImage]]:
        """
        Extract and describe all images from a PDF document.

        Args:
            pdf_path: Path to PDF file
            document_id: Unique document identifier
            context: Optional context (e.g., "MIL-STD-188 specification")

        Returns:
            Dictionary mapping page_number -> List[ProcessedImage]

        Example:
            {
                1: [ProcessedImage(path="img1.png", description="Circuit diagram...", ...)],
                3: [ProcessedImage(path="img2.png", description="Flow chart...", ...)]
            }
        """
        logger.info(f"Processing document: {pdf_path}")
        logger.info(f"Document ID: {document_id}")
        if context:
            logger.info(f"Context: {context}")

        # Step 1: Extract images
        logger.info("Step 1: Extracting images from PDF...")
        extracted_images = self.extraction_service.extract_images_from_pdf(
            pdf_path=pdf_path,
            document_id=document_id
        )

        if not extracted_images:
            logger.warning("No images extracted from document")
            return {}

        # Log extraction stats
        extraction_stats = self.extraction_service.get_extraction_stats(extracted_images)
        logger.info(
            f"Extraction complete: {extraction_stats['total_images']} images "
            f"from {extraction_stats['pages_with_images']} pages"
        )
        logger.info(f"By type: {extraction_stats['images_by_type']}")

        # Step 2: Describe images
        logger.info("Step 2: Generating image descriptions...")
        described_images = self.description_service.describe_images(
            extracted_images=extracted_images,
            context=context
        )

        if not described_images:
            logger.warning("No descriptions generated")
            return {}

        # Log description stats
        description_stats = self.description_service.get_description_stats(described_images)
        logger.info(
            f"Description complete: {description_stats['total_descriptions']} descriptions "
            f"generated"
        )
        logger.info(f"Models used: {description_stats['models_used']}")
        logger.info(f"Avg description length: {description_stats['average_description_length']} chars")

        # Step 3: Convert to unified ProcessedImage format
        logger.info("Step 3: Converting to unified format...")
        processed_images = self._convert_to_processed_images(
            extracted_images,
            described_images,
            document_id
        )

        logger.info(
            f"Processing complete: {sum(len(imgs) for imgs in processed_images.values())} "
            f"processed images"
        )

        return processed_images

    def _convert_to_processed_images(
        self,
        extracted_images: Dict[int, List[ExtractedImage]],
        described_images: Dict[int, List[ImageDescription]],
        document_id: str
    ) -> Dict[int, List[ProcessedImage]]:
        """
        Convert extracted and described images to unified ProcessedImage format.

        Args:
            extracted_images: From ImageExtractionService
            described_images: From ImageDescriptionService
            document_id: Document identifier

        Returns:
            Dictionary of ProcessedImage objects
        """
        processed = {}

        for page_num, extractions in extracted_images.items():
            descriptions = described_images.get(page_num, [])

            # Match extractions with descriptions (should be 1:1)
            page_processed = []
            for i, extracted in enumerate(extractions):
                # Get corresponding description (or create fallback)
                if i < len(descriptions):
                    desc = descriptions[i]
                else:
                    # Shouldn't happen, but handle gracefully
                    logger.warning(
                        f"Missing description for image {i} on page {page_num}, "
                        f"using filename"
                    )
                    desc = ImageDescription(
                        image_path=extracted.image_path,
                        description=f"Image from page {page_num}",
                        page_number=page_num,
                        image_type=extracted.image_type,
                        model_used="fallback"
                    )

                # Create storage path relative to document
                rel_path = str(Path(extracted.image_path).relative_to(self.image_output_dir))

                processed_img = ProcessedImage(
                    image_path=extracted.image_path,
                    page_number=page_num,
                    description=desc.description,
                    image_type=extracted.image_type,
                    model_used=desc.model_used,
                    storage_path=rel_path,
                    width=extracted.width,
                    height=extracted.height,
                    confidence=desc.confidence
                )

                page_processed.append(processed_img)

            if page_processed:
                processed[page_num] = page_processed

        return processed

    def format_for_chromadb_metadata(
        self,
        processed_images: Dict[int, List[ProcessedImage]],
        page_number: int
    ) -> Dict[str, Any]:
        """
        Format processed images for ChromaDB metadata storage.

        Args:
            processed_images: Result from process_document()
            page_number: Page to format metadata for

        Returns:
            Dictionary suitable for ChromaDB metadata field

        Example:
            {
                "images": [
                    {
                        "path": "doc_123/img1.png",
                        "description": "Circuit diagram showing...",
                        "type": "xobject",
                        "model": "gpt-4o"
                    }
                ],
                "image_count": 1,
                "has_diagrams": True
            }
        """
        page_images = processed_images.get(page_number, [])

        if not page_images:
            return {
                "images": [],
                "image_count": 0,
                "has_diagrams": False
            }

        images_metadata = []
        has_diagrams = False

        for img in page_images:
            images_metadata.append({
                "path": img.storage_path,
                "description": img.description,
                "type": img.image_type,
                "model": img.model_used,
                "width": img.width,
                "height": img.height,
                "confidence": img.confidence
            })

            # Check if this is a diagram/drawing
            if img.image_type in ("drawing", "raster"):
                has_diagrams = True
            elif "diagram" in img.description.lower() or "chart" in img.description.lower():
                has_diagrams = True

        return {
            "images": images_metadata,
            "image_count": len(images_metadata),
            "has_diagrams": has_diagrams
        }

    def create_image_reference_text(
        self,
        processed_images: Dict[int, List[ProcessedImage]],
        page_number: int
    ) -> str:
        """
        Create reference text for images on a page.
        Suitable for appending to page text chunks.

        Args:
            processed_images: Result from process_document()
            page_number: Page to create references for

        Returns:
            Formatted reference text

        Example:
            "\\n\\n[Images on this page]\\nFigure 1: Circuit diagram showing power supply connections\\nFigure 2: Timing diagram for clock signals"
        """
        page_images = processed_images.get(page_number, [])

        if not page_images:
            return ""

        lines = ["", "", "[Images on this page]"]

        for i, img in enumerate(page_images, 1):
            # Create reference
            ref = self.description_service.create_image_reference(
                ImageDescription(
                    image_path=img.image_path,
                    description=img.description,
                    page_number=img.page_number,
                    image_type=img.image_type,
                    model_used=img.model_used,
                    confidence=img.confidence
                ),
                image_number=i
            )
            lines.append(ref)

        return "\\n".join(lines)

    def get_processing_summary(
        self,
        processed_images: Dict[int, List[ProcessedImage]]
    ) -> Dict[str, Any]:
        """
        Generate processing summary for logging/reporting.

        Args:
            processed_images: Result from process_document()

        Returns:
            Summary statistics
        """
        total_images = sum(len(imgs) for imgs in processed_images.values())

        type_counts = {}
        model_counts = {}
        confidence_counts = {"high": 0, "medium": 0, "low": 0}

        for images in processed_images.values():
            for img in images:
                # Count by type
                type_counts[img.image_type] = type_counts.get(img.image_type, 0) + 1

                # Count by model
                model_counts[img.model_used] = model_counts.get(img.model_used, 0) + 1

                # Count by confidence
                conf = img.confidence or "medium"
                confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        return {
            "total_images": total_images,
            "pages_with_images": len(processed_images),
            "images_by_type": type_counts,
            "models_used": model_counts,
            "confidence_distribution": confidence_counts
        }
