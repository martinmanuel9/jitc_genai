"""
Image Description Service
Generates natural language descriptions of images using multimodal models.
Uses Microsoft's MarkItDown library for vision-based image understanding.

Capabilities:
- Describe diagrams, charts, schematics
- Extract text from images (OCR fallback)
- Identify key visual elements
- Generate test-procedure-ready descriptions
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Try to import MarkItDown
try:
    from markitdown import MarkItDown
    HAS_MARKITDOWN = True
except ImportError:
    HAS_MARKITDOWN = False
    logger.warning("MarkItDown not available - image description will be disabled")

# Try to import OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("OpenAI not available - multimodal descriptions disabled")


@dataclass
class ImageDescription:
    """Metadata and description for an image"""
    image_path: str
    description: str
    page_number: int
    image_type: str
    model_used: str
    confidence: Optional[str] = None  # "high", "medium", "low"


class ImageDescriptionService:
    """
    Service for generating descriptions of extracted images.

    Uses MarkItDown's multimodal capabilities to:
    1. Analyze image content
    2. Generate natural language descriptions
    3. Extract any text present in images
    4. Identify key visual elements

    Descriptions are optimized for test procedure generation.
    """

    def __init__(
        self,
        llm_model: str = "gpt-4o",  # GPT-4 with vision
        max_workers: int = 4,  # Parallel processing
        fallback_to_filename: bool = True,
        api_key: Optional[str] = None
    ):
        """
        Initialize image description service.

        Args:
            llm_model: Multimodal model to use (must support vision)
            max_workers: Maximum concurrent description requests
            fallback_to_filename: If True, use filename-based descriptions on failure
            api_key: OpenAI API key (uses env var if not provided)
        """
        if not HAS_MARKITDOWN:
            raise ImportError(
                "MarkItDown is required for image descriptions. "
                "Install with: pip install markitdown"
            )

        if not HAS_OPENAI:
            raise ImportError(
                "OpenAI is required for multimodal descriptions. "
                "Install with: pip install openai"
            )

        self.llm_model = llm_model
        self.max_workers = max_workers
        self.fallback_to_filename = fallback_to_filename

        # Initialize OpenAI client
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter"
            )

        try:
            self.openai_client = OpenAI(api_key=self.api_key)
            self.markitdown = MarkItDown(
                llm_client=self.openai_client,
                llm_model=self.llm_model
            )
            logger.info(
                f"ImageDescriptionService initialized with model={llm_model}, "
                f"workers={max_workers}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize MarkItDown: {e}")
            raise

    def describe_images(
        self,
        extracted_images: Dict[int, List],  # page_number -> List[ExtractedImage]
        context: Optional[str] = None
    ) -> Dict[int, List[ImageDescription]]:
        """
        Generate descriptions for all extracted images.

        Args:
            extracted_images: Dictionary mapping page numbers to ExtractedImage lists
            context: Optional context about the document (e.g., "MIL-STD-188 specification")

        Returns:
            Dictionary mapping page numbers to ImageDescription lists

        Example:
            {
                1: [ImageDescription(description="Circuit diagram showing...", ...)],
                3: [ImageDescription(description="Flow chart depicting...", ...)]
            }
        """
        logger.info(f"Describing images from {len(extracted_images)} pages")

        if context:
            logger.info(f"Using context: {context}")

        page_descriptions = {}
        all_images = []

        # Flatten images with page info
        for page_num, images in extracted_images.items():
            for img in images:
                all_images.append((page_num, img))

        if not all_images:
            logger.warning("No images to describe")
            return {}

        logger.info(f"Processing {len(all_images)} total images with {self.max_workers} workers")

        # Process in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all description tasks
            future_to_image = {
                executor.submit(
                    self._describe_single_image,
                    img,
                    page_num,
                    context
                ): (page_num, img)
                for page_num, img in all_images
            }

            # Collect results
            completed = 0
            total = len(future_to_image)

            for future in as_completed(future_to_image):
                page_num, img = future_to_image[future]
                completed += 1

                try:
                    description = future.result()

                    if description:
                        if page_num not in page_descriptions:
                            page_descriptions[page_num] = []

                        page_descriptions[page_num].append(description)
                        logger.info(
                            f" [{completed}/{total}] Described image: "
                            f"page {page_num}, {img.image_type}"
                        )
                    else:
                        logger.warning(
                            f"  [{completed}/{total}] No description generated: "
                            f"page {page_num}, {img.image_type}"
                        )

                except Exception as e:
                    logger.error(
                        f" [{completed}/{total}] Failed to describe image "
                        f"on page {page_num}: {e}"
                    )

        logger.info(
            f"Description complete: {sum(len(d) for d in page_descriptions.values())} "
            f"descriptions generated"
        )

        return page_descriptions

    def _describe_single_image(
        self,
        extracted_image,  # ExtractedImage
        page_number: int,
        context: Optional[str] = None
    ) -> Optional[ImageDescription]:
        """
        Generate description for a single image.

        Args:
            extracted_image: ExtractedImage object
            page_number: Page number
            context: Optional document context

        Returns:
            ImageDescription or None if description fails
        """
        image_path = extracted_image.image_path

        try:
            logger.debug(f"Describing image: {image_path}")

            # Use MarkItDown to describe the image
            result = self.markitdown.convert(image_path)

            if result and result.text_content:
                description_text = result.text_content.strip()

                # Enhance description with context if provided
                if context and description_text:
                    description_text = self._enhance_description_with_context(
                        description_text,
                        context
                    )

                # Create description object
                return ImageDescription(
                    image_path=image_path,
                    description=description_text,
                    page_number=page_number,
                    image_type=extracted_image.image_type,
                    model_used=self.llm_model,
                    confidence="high" if len(description_text) > 50 else "low"
                )

            else:
                logger.warning(f"MarkItDown returned empty description for {image_path}")

                # Fallback to filename-based description
                if self.fallback_to_filename:
                    return self._filename_based_description(
                        extracted_image,
                        page_number
                    )

                return None

        except Exception as e:
            logger.error(f"Image description failed for {image_path}: {e}")

            # Fallback
            if self.fallback_to_filename:
                return self._filename_based_description(extracted_image, page_number)

            return None

    def _enhance_description_with_context(
        self,
        description: str,
        context: str
    ) -> str:
        """
        Enhance image description with document context.

        Args:
            description: Base description from MarkItDown
            context: Document context

        Returns:
            Enhanced description
        """
        # If description is very short, prefix with context
        if len(description) < 100:
            return f"[{context}] {description}"

        # Otherwise return as-is
        return description

    def _filename_based_description(
        self,
        extracted_image,  # ExtractedImage
        page_number: int
    ) -> ImageDescription:
        """
        Create a basic description based on filename and metadata.
        Fallback when multimodal description fails.

        Args:
            extracted_image: ExtractedImage object
            page_number: Page number

        Returns:
            ImageDescription with filename-based description
        """
        filename = Path(extracted_image.image_path).name
        img_type = extracted_image.image_type

        # Create basic description
        if img_type == "xobject":
            desc = f"Embedded image: {filename}"
        elif img_type == "raster":
            desc = f"Page content visualization: {filename}"
        elif img_type == "drawing":
            desc = f"Vector diagram: {filename}"
        else:
            desc = f"Image content: {filename}"

        # Add dimensions if available
        if extracted_image.width and extracted_image.height:
            desc += f" ({extracted_image.width}x{extracted_image.height} pixels)"

        return ImageDescription(
            image_path=extracted_image.image_path,
            description=desc,
            page_number=page_number,
            image_type=img_type,
            model_used="filename_fallback",
            confidence="low"
        )

    def create_image_reference(
        self,
        image_description: ImageDescription,
        image_number: int
    ) -> str:
        """
        Create a reference string for use in test procedures.

        Args:
            image_description: ImageDescription object
            image_number: Sequential image number in document

        Returns:
            Reference string like "See Figure 3.2: Circuit diagram showing..."

        Example:
            "See Figure 1: Block diagram showing signal flow between modules"
        """
        desc_preview = image_description.description[:100]
        if len(image_description.description) > 100:
            desc_preview += "..."

        return f"See Figure {image_number}: {desc_preview}"

    def get_description_stats(
        self,
        page_descriptions: Dict[int, List[ImageDescription]]
    ) -> Dict[str, Any]:
        """
        Generate statistics about image descriptions.

        Args:
            page_descriptions: Result from describe_images()

        Returns:
            Statistics dictionary
        """
        total_descriptions = sum(len(descs) for descs in page_descriptions.values())

        model_counts = {}
        confidence_counts = {"high": 0, "medium": 0, "low": 0}

        for descriptions in page_descriptions.values():
            for desc in descriptions:
                # Count by model
                model = desc.model_used
                model_counts[model] = model_counts.get(model, 0) + 1

                # Count by confidence
                conf = desc.confidence or "medium"
                confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        avg_desc_length = 0
        if total_descriptions > 0:
            total_length = sum(
                len(desc.description)
                for descs in page_descriptions.values()
                for desc in descs
            )
            avg_desc_length = total_length / total_descriptions

        return {
            "total_descriptions": total_descriptions,
            "pages_with_descriptions": len(page_descriptions),
            "models_used": model_counts,
            "confidence_distribution": confidence_counts,
            "average_description_length": int(avg_desc_length)
        }
