"""
Image Description Service
Generates natural language descriptions of images using local LLaVA (Ollama).

Capabilities:
- Describe diagrams, charts, schematics
- Extract text from images (OCR fallback)
- Identify key visual elements
- Generate test-procedure-ready descriptions
"""

import os
import base64
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)


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

    Uses local LLaVA via Ollama to:
    1. Analyze image content
    2. Generate natural language descriptions
    3. Extract any text present in images
    4. Identify key visual elements

    Descriptions are optimized for test procedure generation.
    """

    def __init__(
        self,
        llm_model: str = "llava:7b",
        max_workers: int = 4,
        fallback_to_filename: bool = True,
        api_key: Optional[str] = None,
        ollama_url: Optional[str] = None,
    ):
        """
        Initialize image description service.

        Args:
            llm_model: Multimodal model to use (must support vision)
            max_workers: Maximum concurrent description requests
            fallback_to_filename: If True, use filename-based descriptions on failure
            api_key: Deprecated; retained for compatibility
            ollama_url: Ollama base URL (uses env var if not provided)
        """
        self.llm_model = llm_model
        self.max_workers = max_workers
        self.fallback_to_filename = fallback_to_filename
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://ollama:11434")

        logger.info(
            "ImageDescriptionService initialized with model=%s, workers=%s",
            llm_model,
            max_workers,
        )

    def describe_images(
        self,
        extracted_images: Dict[int, List],  # page_number -> List[ExtractedImage]
        context: Optional[str] = None,
    ) -> Dict[int, List[ImageDescription]]:
        """
        Generate descriptions for all extracted images.

        Args:
            extracted_images: Dictionary mapping page numbers to ExtractedImage lists
            context: Optional context about the document (e.g., "MIL-STD-188 specification")

        Returns:
            Dictionary mapping page numbers to ImageDescription lists
        """
        logger.info("Describing images from %s pages", len(extracted_images))

        described_images: Dict[int, List[ImageDescription]] = {}
        futures = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for page_number, images in extracted_images.items():
                for image in images:
                    futures.append(
                        executor.submit(
                            self._describe_single_image,
                            image,
                            page_number,
                            context,
                        )
                    )

            for future in as_completed(futures):
                description = future.result()
                described_images.setdefault(description.page_number, []).append(description)

        return described_images

    def _describe_single_image(self, image: Any, page_number: int, context: Optional[str]) -> ImageDescription:
        image_path = self._get_image_attr(image, "image_path")
        image_type = self._get_image_attr(image, "image_type", "unknown")

        description = None
        if image_path:
            description = self._describe_with_ollama(image_path, context)

        if not description and self.fallback_to_filename:
            filename = Path(image_path).name if image_path else "image"
            description = f"Image: {filename}"

        model_used = self.llm_model if description and "Ollama Vision" in description else "fallback"

        return ImageDescription(
            image_path=image_path or "",
            description=description or "",
            page_number=page_number,
            image_type=image_type,
            model_used=model_used,
            confidence=None,
        )

    def _describe_with_ollama(self, image_path: str, context: Optional[str]) -> Optional[str]:
        if not os.path.exists(image_path):
            logger.warning("Image file not found: %s", image_path)
            return None

        try:
            with open(image_path, "rb") as img_file:
                img_data = base64.b64encode(img_file.read()).decode()

            prompt = (
                "Describe this image succinctly, focusing on any text and technical details."
            )
            if context:
                prompt = f"Context: {context}\n\n{prompt}"

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "images": [img_data],
                    "stream": False,
                },
                timeout=(5, 20),
            )

            if response.status_code != 200:
                logger.warning(
                    "Ollama API returned status %s for %s",
                    response.status_code,
                    image_path,
                )
                return None

            result = response.json()
            description = (result.get("response") or "").strip()
            if description:
                return f"Ollama Vision ({self.llm_model}): {description}"

            return None

        except Exception as e:
            logger.warning("Ollama vision failed for %s: %s", image_path, e)
            return None

    @staticmethod
    def _get_image_attr(image: Any, attr: str, default: Optional[str] = None) -> Optional[str]:
        if hasattr(image, attr):
            return getattr(image, attr)
        if isinstance(image, dict):
            return image.get(attr, default)
        return default
