# src/fastapi/services/document_ingestion_service.py
"""
Document Ingestion Service
Handles document processing, chunking, and embedding generation
"""

import os
import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import redis
import json
import uuid
from datetime import datetime
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from markitdown import MarkItDown
from PyPDF2 import PdfReader
import pytesseract
from PIL import Image
import requests
import base64
import numpy as np
from dotenv import load_dotenv
import cv2
import asyncio
import functools
from zipfile import ZipFile
from bs4 import BeautifulSoup

# Position-aware image placement imports
from .position_aware_extraction import (
    extract_images_with_positions,
    add_text_anchors_to_images
)
from .position_aware_chunking import (
    page_based_chunking_with_positions
)

logger = logging.getLogger("DOC_INGESTION_SERVICE")

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

VISION_CONFIG = {
            "openai_enabled": bool(openai_api_key),
            "ollama_enabled": True,
            "huggingface_enabled": True,
            "enhanced_local_enabled": True,
            "ollama_url": os.getenv("OLLAMA_URL", "http://ollama:11434"),
            "ollama_model": os.getenv("OLLAMA_VISION_MODEL", "llava:7b"),
            "huggingface_model": os.getenv("HUGGINGFACE_VISION_MODEL", "Salesforce/blip-image-captioning-base"),
            # Ollama vision model mappings
            "ollama_models": {
                "llava_7b": "llava:7b",
                "llava_13b": "llava:13b",
                "granite_vision_2b": "granite3.2-vision:2b"
            }
        }

# Image storage directory
IMAGES_DIR = os.getenv("IMAGES_STORAGE_DIR", os.path.join(os.getcwd(), "stored_images"))
try:
    os.makedirs(IMAGES_DIR, exist_ok=True)
except PermissionError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Permission denied creating images directory at {IMAGES_DIR}: {e}")
    logger.warning(f"Please ensure write permissions for {IMAGES_DIR} or set IMAGES_STORAGE_DIR env variable")
    # Try to use a fallback directory in /tmp
    import tempfile
    IMAGES_DIR = os.path.join(tempfile.gettempdir(), "stored_images")
    logger.info(f"Using fallback directory: {IMAGES_DIR}")
    os.makedirs(IMAGES_DIR, exist_ok=True)

_hf_processor = None
_hf_model = None


# =============================================================================
# Module-level initialization (replaces DocumentIngestionService class)
# =============================================================================

# ChromaDB client - lazy initialization
CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

_chroma_client = None

def get_chroma_client():
    """Get or create ChromaDB client with lazy initialization."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT
        )
    return _chroma_client

# For backward compatibility - will be lazily initialized on first access
class LazyChromaClient:
    def __getattr__(self, name):
        return getattr(get_chroma_client(), name)

chroma_client = LazyChromaClient()

# Embedding model (single instance)
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/multi-qa-mpnet-base-dot-v1"
)
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

# Redis for job tracking
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ChromaDB persistence directory (for legacy compatibility)
PERSIST_DIR = os.getenv("PERSIST_DIRECTORY", "/chroma/chroma")

# Feature flag for position-aware extraction and chunking
USE_POSITION_AWARE = os.getenv("USE_POSITION_AWARE_EXTRACTION", "true").lower() == "true"

logger.info("Document Ingestion Service initialized")
logger.info(f"ChromaDB: {CHROMA_HOST}:{CHROMA_PORT}")
logger.info(f"Embedding model: {EMBEDDING_MODEL_NAME}")
logger.info(f"Redis: {REDIS_URL}")
logger.info(f"Position-aware extraction: {'ENABLED' if USE_POSITION_AWARE else 'DISABLED'}")


# =============================================================================
# Image Description Functions
# =============================================================================

def get_markitdown_instance(api_key_override: str = None):
    """Create MarkItDown instance with proper configuration"""
    api_key = api_key_override or openai_api_key
    
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            return MarkItDown(llm_client=client, llm_model="gpt-4o-mini")
        except Exception as e:
            logger.error(f"Failed to create OpenAI MarkItDown instance: {e}")
            return MarkItDown()
    else:
        logger.info("No OpenAI API key available, using basic MarkItDown")
        return MarkItDown()


async def describe_with_openai_markitdown(image_path: str, api_key: str = openai_api_key) -> Optional[str]:
    """Use OpenAI via MarkItDown for image description"""
    try:
        if not (api_key or openai_api_key):
            logger.info("No Open AI API key available for image description")
            return None
            
        # Verify image file exists and is readable
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None
            
        # Verify it's a valid image
        try:
            with Image.open(image_path) as img:
                img.verify()
        except Exception as e:
            logger.error(f"Invalid image file {image_path}: {e}")
            return None
            
        md_instance = get_markitdown_instance(api_key)
        fn = functools.partial(md_instance.convert, image_path)
        
        try:
            # 60s should be plenty for a single image—tune to your needs
            result =  await asyncio.wait_for(asyncio.to_thread(fn), timeout=60)
        except asyncio.TimeoutError:
            logger.warning(f"OpenAI vision timed out for {image_path}")
            return None
        
        # Extract text content properly
        desc = None
        if hasattr(result, 'text_content'):
            desc = result.text_content
        elif hasattr(result, 'content'):
            desc = result.content
        else:
            desc = str(result)
        
        if desc and desc.strip() and len(desc.strip()) > 10:
            # Clean up the description
            desc_clean = desc.strip()
            # Remove common MarkItDown artifacts
            if desc_clean.startswith("!["):
                # If it's just markdown image syntax, extract alt text
                if "](" in desc_clean:
                    alt_text = desc_clean.split("](")[0][2:]  # Remove ![
                    if alt_text:
                        desc_clean = alt_text
            
            return f"OpenAI Vision: {desc_clean}"
        
        logger.warning(f"OpenAI MarkItDown returned empty or too short description for {image_path}")
        return None
        
    except Exception as e:
        logger.warning(f"OpenAI MarkItDown failed for {image_path}: {e}")
        return None
    
def describe_with_ollama_vision(image_path: str, model_key: str = None) -> Optional[str]:
    """Use Ollama vision model for image description

    Args:
        image_path: Path to the image file
        model_key: Key for the specific Ollama model (e.g., 'llava_7b', 'llava_13b', 'granite_vision_2b')
                   If None, uses the default model from VISION_CONFIG
    """
    try:
        if not VISION_CONFIG["ollama_enabled"]:
            return None

        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None

        # Determine which model to use
        if model_key and model_key in VISION_CONFIG.get("ollama_models", {}):
            model_name = VISION_CONFIG["ollama_models"][model_key]
        else:
            model_name = VISION_CONFIG['ollama_model']

        # Read and encode image
        with open(image_path, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode()

        # Ollama API call
        response = requests.post(
            f"{VISION_CONFIG['ollama_url']}/api/generate",
            json={
                "model": model_name,
                "prompt": "Describe this image succinctly, focusing on the text found in the image. Be specific and descriptive.",
                "images": [img_data],
                "stream": False
            },
            timeout= (10, 60)
        )

        if response.status_code == 200:
            result = response.json()
            description = result.get("response", "").strip()
            if description and len(description) > 10:
                return f"Ollama Vision ({model_name}): {description}"
        else:
            logger.warning(f"Ollama API returned status {response.status_code} for model {model_name}")

        return None

    except Exception as e:
        logger.warning(f"Ollama vision model {model_key or 'default'} failed for {image_path}: {e}")
        return None


def describe_with_huggingface_vision(image_path: str) -> Optional[str]:
    """Use Hugging Face vision model for image description"""
    try:
        if not VISION_CONFIG["huggingface_enabled"]:
            return None
            
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None
            
        global _hf_processor, _hf_model
        
        # Load models once and cache them
        if _hf_processor is None or _hf_model is None:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            logger.info(f"Loading HuggingFace model: {VISION_CONFIG['huggingface_model']}")
            _hf_processor = BlipProcessor.from_pretrained(VISION_CONFIG['huggingface_model'])
            _hf_model = BlipForConditionalGeneration.from_pretrained(VISION_CONFIG['huggingface_model'])
        
        # Process image
        image = Image.open(image_path)
        inputs = _hf_processor(image, return_tensors="pt")
        
        # Generate description
        out = _hf_model.generate(**inputs, max_length=50, num_beams=4)
        description = _hf_processor.decode(out[0], skip_special_tokens=True)
        
        if description and len(description) > 5:
            return f"HuggingFace BLIP: {description}"
        
        return None
        
    except Exception as e:
        logger.warning(f"HuggingFace vision model failed for {image_path}: {e}")
        # Disable HuggingFace for subsequent attempts if it fails
        VISION_CONFIG["huggingface_enabled"] = False
        return None

def enhanced_local_image_analysis(image_path: str) -> str:
    """Enhanced local image analysis using OpenCV and PIL"""
    try:
        if not os.path.exists(image_path):
            return f"Image file not found: {Path(image_path).name}"
            
        # Load images
        img_pil = Image.open(image_path)
        img_cv = cv2.imread(image_path)
        
        # Basic info
        width, height = img_pil.size
        mode = img_pil.mode
        format_info = img_pil.format or "Unknown"
        
        description_parts = []
        
        # Size classification
        total_pixels = width * height
        if total_pixels > 2000000:  # > 2MP
            size_desc = "high-resolution"
        elif total_pixels > 500000:  # > 0.5MP
            size_desc = "medium-resolution"
        else:
            size_desc = "small"
        
        description_parts.append(f"{size_desc} {format_info.lower()} image")
        
        # Advanced color analysis
        if mode == 'RGB' and img_cv is not None:
            # Convert to different color spaces for analysis
            hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
            
            # Analyze color distribution
            hist_hue = cv2.calcHist([hsv], [0], None, [180], [0, 180])
            dominant_hue = np.argmax(hist_hue)
            
            # Color classification based on HSV
            if dominant_hue < 10 or dominant_hue > 170:
                color_desc = "with red/pink tones"
            elif 10 <= dominant_hue < 25:
                color_desc = "with orange/yellow tones"
            elif 25 <= dominant_hue < 75:
                color_desc = "with green tones"
            elif 75 <= dominant_hue < 130:
                color_desc = "with blue/cyan tones"
            else:
                color_desc = "with purple/magenta tones"
            
            # Check saturation and value
            avg_saturation = np.mean(hsv[:, :, 1])
            avg_brightness = np.mean(hsv[:, :, 2])
            
            if avg_saturation < 50:
                color_desc += " (muted/grayscale)"
            elif avg_saturation > 150:
                color_desc += " (vibrant)"
            
            if avg_brightness < 85:
                color_desc += " and dark lighting"
            elif avg_brightness > 170:
                color_desc += " and bright lighting"
            
            description_parts.append(color_desc)
            
            # Shape and edge detection
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # Contour detection
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) > 20:
                description_parts.append("containing many objects or complex details")
            elif len(contours) > 5:
                description_parts.append("containing several distinct elements")
            else:
                description_parts.append("with simple composition")
            
            # Text detection heuristic
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (18, 18))
            morph = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
            text_contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            text_like_regions = 0
            for contour in text_contours:
                _, _, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0
                if 0.1 < aspect_ratio < 10 and w > 10 and h > 5:
                    text_like_regions += 1
            
            if text_like_regions > 2:
                description_parts.append("likely containing text or symbols")
        
        # OCR attempt
        try:
            text = pytesseract.image_to_string(img_pil, config='--psm 11').strip()
            if text and len(text) > 2:
                # Clean and limit text
                text_clean = ' '.join(text.split())
                if len(text_clean) > 100:
                    text_desc = f"with readable text including: '{text_clean[:100]}...'"
                else:
                    text_desc = f"with readable text: '{text_clean}'"
                description_parts.append(text_desc)
        except Exception as ocr_error:
            logger.debug(f"OCR failed for {image_path}: {ocr_error}")
        
        # Combine description
        final_desc = "Enhanced analysis: " + ", ".join(description_parts) + f" ({width}x{height}px)"
        return final_desc
        
    except Exception as e:
        logger.warning(f"Enhanced local analysis failed for {image_path}: {e}")
        return basic_image_analysis(image_path)
    
def basic_image_analysis(image_path: str) -> str:
    """Basic image analysis fallback"""
    try:
        if not os.path.exists(image_path):
            return f"Image file not found: {Path(image_path).name}"
            
        img = Image.open(image_path)
        width, height = img.size
        mode = img.mode
        format_info = img.format or "Unknown"
        
        # Try OCR
        try:
            text = pytesseract.image_to_string(img).strip()
        except:
            text = ""
        
        description_parts = [
            f"Basic analysis: {format_info} image",
            f"{width}x{height} pixels",
            f"{mode} color mode"
        ]
        
        if text:
            description_parts.append(f"containing text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        else:
            description_parts.append("no readable text detected")
        
        return ", ".join(description_parts)
        
    except Exception as e:
        logger.error(f"Basic image analysis failed for {image_path}: {e}")
        return f"Image file: {Path(image_path).name} (analysis failed)"

async def describe_images_for_pages(
    pages_data: List[Dict],
    api_key_override=None,
    run_all_models: bool = True,
    enabled_models: set[str] = frozenset(),
    vision_flags: dict[str,bool] = {}
) -> List[Dict]:
    for page in pages_data:
        descs = []
        for img_item in page["images"]:
            # Handle both legacy (string path) and position-aware (dict) formats
            if isinstance(img_item, dict):
                # Position-aware format: extract storage_path from dictionary
                img_path = img_item.get("storage_path", "")
            else:
                # Legacy format: img_item is already the path string
                img_path = img_item

            if not img_path:
                logger.warning(f"Skipping image with no path: {img_item}")
                descs.append("No image path available")
                continue

            if run_all_models:
                all_desc = {}
                if "openai" in enabled_models and vision_flags.get("openai", False):
                    d = await describe_with_openai_markitdown(img_path, api_key_override)
                    if d:
                        all_desc["OpenAI"] = d
                # Handle specific Ollama vision models
                for ollama_key in ["llava_7b", "llava_13b", "granite_vision_2b"]:
                    if ollama_key in enabled_models and vision_flags.get(ollama_key, False):
                        d = describe_with_ollama_vision(img_path, model_key=ollama_key)
                        if d:
                            all_desc[f"Ollama_{ollama_key}"] = d
                # Legacy ollama support (backward compatibility)
                if "ollama" in enabled_models and vision_flags.get("ollama", False):
                    d = describe_with_ollama_vision(img_path)
                    if d: all_desc["Ollama"] = d
                if "huggingface" in enabled_models and vision_flags.get("huggingface", False):
                    d = describe_with_huggingface_vision(img_path)
                    if d: all_desc["HuggingFace"] = d
                if "enhanced_local" in enabled_models and vision_flags.get("enhanced_local", False):
                    d = enhanced_local_image_analysis(img_path)
                    if d: all_desc["Enhanced Local"] = d

                # always include basic fallback
                all_desc["Basic Fallback"] = basic_image_analysis(img_path)
                descs.append(create_combined_description(all_desc, Path(img_path).name))

            else:
                # first‐success only among enabled & flagged
                d = None
                if "openai" in enabled_models and vision_flags.get("openai", False):
                    d = await describe_with_openai_markitdown(img_path, api_key_override)
                # Try specific Ollama models
                for ollama_key in ["llava_7b", "llava_13b", "granite_vision_2b"]:
                    if not d and ollama_key in enabled_models and vision_flags.get(ollama_key, False):
                        d = describe_with_ollama_vision(img_path, model_key=ollama_key)
                # Legacy ollama support (backward compatibility)
                if not d and "ollama" in enabled_models and vision_flags.get("ollama", False):
                    d = describe_with_ollama_vision(img_path)
                if not d and "huggingface" in enabled_models and vision_flags.get("huggingface", False):
                    d = describe_with_huggingface_vision(img_path)
                if not d and "enhanced_local" in enabled_models and vision_flags.get("enhanced_local", False):
                    d = enhanced_local_image_analysis(img_path)
                descs.append(d or basic_image_analysis(img_path))

        page["image_descriptions"] = descs
    return pages_data

def extract_and_store_images_from_file(file_content: bytes, filename: str, temp_dir: str, doc_id: str) -> List[Dict]:
    """Fixed image extraction from PDF with better error handling"""
    pages_data = []

    try:
        temp_pdf_path = os.path.join(temp_dir, filename)
        with open(temp_pdf_path, 'wb') as f:
            f.write(file_content)

        reader = PdfReader(temp_pdf_path)
        logger.info(f"Successfully opened PDF with {len(reader.pages)} pages")

        for page_num, page in enumerate(reader.pages, 1):
            page_images = []
            
            try:
                # Get page resources
                if "/Resources" not in page:
                    logger.info(f"Page {page_num}: No resources found")
                    pages_data.append({
                        "page": page_num,
                        "images": page_images,
                        "text": None
                    })
                    continue
                    
                resources = page["/Resources"]
                
                # Check if resources is an IndirectObject and resolve it
                if hasattr(resources, 'get_object'):
                    resources = resources.get_object()
                
                # Check for XObject (images)
                if "/XObject" not in resources:
                    logger.info(f"Page {page_num}: No XObjects found")
                    pages_data.append({
                        "page": page_num,
                        "images": page_images,
                        "text": None
                    })
                    continue
                
                xobjects = resources["/XObject"]
                
                # Handle IndirectObject for XObjects
                if hasattr(xobjects, 'get_object'):
                    xobjects = xobjects.get_object()
                
                # Iterate through XObjects
                for obj_name in xobjects:
                    try:
                        xobj = xobjects[obj_name]
                        
                        # Handle IndirectObject
                        if hasattr(xobj, 'get_object'):
                            xobj = xobj.get_object()
                        
                        # Check if it's an image
                        if xobj.get("/Subtype") == "/Image":
                            try:
                                # Get image data FIRST
                                data = xobj.get_data()
                                filters = xobj.get('/Filter')

                                # if it's neither DCT (jpg) nor Flate (png), try PIL from-memory:
                                if filters not in ('/DCTDecode','/FlateDecode'):
                                    img_ext = 'png'
                                    try:
                                        from io import BytesIO
                                        im = Image.open(BytesIO(data))
                                        im = im.convert("RGB")
                                        im.save(img_storage_path, format="PNG")
                                        logger.info(f"Forced-PNG from {filters}: {img_filename}")
                                    except Exception:
                                        # fallback to writing raw bytes and hope verify() passes
                                        pass
                                
                                # Determine file extension
                                if filters == '/DCTDecode':
                                    img_ext = 'jpg'
                                elif filters == '/FlateDecode':
                                    img_ext = 'png'
                                else:
                                    img_ext = 'png'  # Default to PNG
                                
                                # Create filename
                                img_filename = f"{doc_id}_page_{page_num}_{obj_name[1:]}.{img_ext}"
                                img_storage_path = os.path.join(IMAGES_DIR, img_filename)
                                
                                # Save image
                                with open(img_storage_path, "wb") as img_file:
                                    img_file.write(data)
                                    
                                # — normalize any “png” (and catch /Filter lists like ['/FlateDecode', ...])
                                if img_ext == 'png':
                                    try:
                                        with Image.open(img_storage_path) as im:
                                            # convert any weird bit-depths/modes into RGB
                                            if im.mode not in ("RGB", "L"):
                                                im = im.convert("RGB")
                                            # re-save so the file on disk is a bona-fide PNG
                                            im.save(img_storage_path)
                                        logger.info(f"Normalized PNG: {img_filename}")
                                    except Exception as e:
                                        logger.warning(f"Could not normalize {img_filename}: {e}")
                                
                                # Verify image was saved and is valid
                                if os.path.exists(img_storage_path) and os.path.getsize(img_storage_path) > 0:
                                    # Try to open with PIL to verify it's a valid image
                                    try:
                                        with Image.open(img_storage_path) as test_img:
                                            test_img.verify()
                                        page_images.append(img_storage_path)
                                        logger.info(f"Successfully stored and verified image: {img_filename}")
                                    except Exception as img_verify_error:
                                        logger.warning(f"Invalid image file created: {img_filename}, error: {img_verify_error}")
                                        # Remove invalid file
                                        if os.path.exists(img_storage_path):
                                            os.remove(img_storage_path)
                                else:
                                    logger.warning(f"Image file was not created or is empty: {img_filename}")
                                    
                            except Exception as e:
                                logger.error(f"Failed to extract image {obj_name} from page {page_num}: {e}")
                                
                    except Exception as e:
                        logger.error(f"Error processing XObject {obj_name} on page {page_num}: {e}")
                        
            except Exception as e:
                logger.error(f"Error processing page {page_num}: {e}")
            
            pages_data.append({
                "page": page_num,
                "images": page_images,
                "text": None
            })
            
            logger.info(f"Page {page_num}: Found {len(page_images)} images")

    except Exception as e:
        logger.error(f"Error extracting images from {filename}: {e}")

    logger.info(f"Total images extracted from {filename}: {sum(len(p['images']) for p in pages_data)}")
    return pages_data


def extract_images_with_position_support(
    file_content: bytes,
    filename: str,
    temp_dir: str,
    doc_id: str,
    use_positions: bool = True
) -> List[Dict[str, Any]]:
    """
    Wrapper that supports both legacy and position-aware extraction.

    Args:
        file_content: PDF file bytes
        filename: Original filename
        temp_dir: Temporary directory
        doc_id: Document ID
        use_positions: If True, use position-aware extraction

    Returns:
        List of page data with images
    """
    if use_positions and USE_POSITION_AWARE:
        logger.info(f"Using position-aware extraction for {filename}")
        try:
            pages_data = extract_images_with_positions(
                file_content=file_content,
                filename=filename,
                temp_dir=temp_dir,
                doc_id=doc_id,
                images_dir=IMAGES_DIR
            )

            # Add text anchors for better position matching
            pages_data = add_text_anchors_to_images(
                pages_data,
                context_chars=100
            )

            logger.info(f"Position-aware extraction successful: {sum(len(p['images']) for p in pages_data)} images")
            return pages_data

        except Exception as e:
            logger.error(f"Position-aware extraction failed, falling back to legacy: {e}")
            # Fall through to legacy extraction

    # Legacy extraction (current implementation)
    logger.info(f"Using legacy extraction for {filename}")
    return extract_and_store_images_from_file(file_content, filename, temp_dir, doc_id)


def extract_text_by_page(file_content: bytes, filename: str, temp_dir: str) -> List[Dict]:
    """Extract text per page from a PDF using PyPDF2."""
    texts: List[Dict] = []
    try:
        temp_pdf_path = os.path.join(temp_dir, filename)
        if not os.path.exists(temp_pdf_path):
            with open(temp_pdf_path, 'wb') as f:
                f.write(file_content)
        reader = PdfReader(temp_pdf_path)
        for page_num, page in enumerate(reader.pages, 1):
            try:
                txt = page.extract_text() or ""
            except Exception as e:
                logger.warning(f"Text extraction failed on page {page_num}: {e}")
                txt = ""
            texts.append({"page": page_num, "text": txt})
    except Exception as e:
        logger.error(f"Error extracting text by page from {filename}: {e}")
    return texts

def use_structure_preserving_upload() -> bool:
    """Check if we should use structure-preserving upload instead of chunking"""
    return os.getenv("USE_STRUCTURE_PRESERVING_UPLOAD", "true").lower() == "true"

def structure_preserving_process(content: str, images_data: List[Dict], document_name: str) -> List[Dict]:
    """Process document while preserving its natural structure (sections, pages, etc.)

    Used when USE_STRUCTURE_PRESERVING_UPLOAD=true (default)
    Detects and preserves:
    - Page boundaries
    - Section headers (numbered sections, APPENDIX, etc.)
    - Document structure for better semantic chunking
    """
    import re

    chunks = []
    
    # Try to detect if this is a multi-page document
    page_separators = [
        r'\n\s*Page \d+',
        r'\n\s*\d+\s*\n\s*MIL-STD',
        r'\n\s*APPENDIX [A-Z]',
        r'\n\s*\d+\.\s+[A-Z][A-Za-z\s]+\n',
        r'\n\s*[A-Z][A-Z\s]{10,}\s*\n'
    ]
    
    # First, try to split by pages if page markers exist
    page_splits = []
    for pattern in page_separators:
        if re.search(pattern, content, re.MULTILINE):
            page_splits = re.split(pattern, content)
            break
    
    if len(page_splits) > 1:
        # Process as pages
        logger.info(f"Processing {document_name} as {len(page_splits)} pages")
        for page_idx, page_content in enumerate(page_splits):
            if page_content.strip():
                # Find images that belong to this page
                page_images = find_images_for_section(page_content, images_data)
                
                chunk_data = {
                    "content": page_content.strip(),
                    "chunk_index": page_idx,
                    "images": page_images,
                    "page_number": page_idx + 1,
                    "section_type": "page",
                    "section_title": extract_section_title_from_content(page_content),
                    "has_images": len(page_images) > 0,
                    "start_position": page_idx * 2000,  # Estimated
                    "end_position": (page_idx + 1) * 2000  # Estimated
                }
                chunks.append(chunk_data)
    else:
        # Process as sections based on headers
        sections = extract_document_sections_from_content(content)
        logger.info(f"Processing {document_name} as {len(sections)} sections")
        
        for section_idx, (section_title, section_content) in enumerate(sections.items()):
            if section_content.strip():
                # Find images that belong to this section
                section_images = find_images_for_section(section_content, images_data)
                
                chunk_data = {
                    "content": section_content.strip(),
                    "chunk_index": section_idx,
                    "images": section_images,
                    "section_number": section_idx + 1,
                    "section_type": "logical_section",
                    "section_title": section_title,
                    "has_images": len(section_images) > 0,
                    "start_position": section_idx * 3000,  # Estimated
                    "end_position": (section_idx + 1) * 3000  # Estimated
                }
                chunks.append(chunk_data)
    
    # If no structure detected, fall back to one large chunk
    if not chunks:
        chunk_data = {
            "content": content.strip(),
            "chunk_index": 0,
            "images": images_data,
            "section_number": 1,
            "section_type": "complete_document",
            "section_title": document_name,
            "has_images": len(images_data) > 0,
            "start_position": 0,
            "end_position": len(content)
        }
        chunks.append(chunk_data)
    
    logger.info(f"Structure-preserving processing created {len(chunks)} chunks for {document_name}")
    return chunks

def extract_document_sections_from_content(content: str) -> Dict[str, str]:
    """Extract logical sections from document content based on headers"""
    import re
    
    sections = {}
    lines = content.split('\n')
    current_section_title = "Introduction"
    current_section_content = []
    
    for line in lines:
        line_clean = line.strip()
        
        # Check for section headers - various patterns for military standards
        is_section_header = False
        header_title = ""
        
        if line_clean:
            # Pattern 1: Numbered sections (4.1, 5.1.13, etc.)
            if re.match(r'^\d+(\.\d+)*\.?\s+[A-Z]', line_clean):
                is_section_header = True
                header_title = line_clean
            # Pattern 2: ALL CAPS headers
            elif line_clean.isupper() and len(line_clean.split()) <= 8 and len(line_clean) > 5:
                is_section_header = True
                header_title = line_clean
            # Pattern 3: APPENDIX headers
            elif line_clean.startswith(('APPENDIX', 'CHAPTER', 'SECTION', 'PART')):
                is_section_header = True
                header_title = line_clean
            # Pattern 4: Headers with specific keywords
            elif any(keyword in line_clean.upper() for keyword in ['REQUIREMENTS', 'SPECIFICATIONS', 'PROCEDURES', 'TESTING', 'CONFIGURATION']):
                if len(line_clean.split()) <= 10:
                    is_section_header = True
                    header_title = line_clean
        
        if is_section_header and current_section_content:
            # Save previous section
            sections[current_section_title] = '\n'.join(current_section_content)
            current_section_title = header_title
            current_section_content = []
        else:
            current_section_content.append(line)
    
    # Add the last section
    if current_section_content:
        sections[current_section_title] = '\n'.join(current_section_content)
    
    return sections

def extract_section_title_from_content(content: str) -> str:
    """Extract a meaningful title from section content"""
    import re
    
    lines = content.split('\n')
    for line in lines[:5]:  # Check first 5 lines
        line_clean = line.strip()
        if line_clean:
            # Look for numbered sections or headers
            if re.match(r'^\d+(\.\d+)*\.?\s+[A-Z]', line_clean):
                return line_clean
            elif line_clean.isupper() and len(line_clean.split()) <= 8:
                return line_clean
            elif line_clean.startswith(('APPENDIX', 'CHAPTER', 'SECTION')):
                return line_clean
    
    # Fallback to first substantial line
    for line in lines[:10]:
        line_clean = line.strip()
        if len(line_clean) > 10 and len(line_clean) < 100:
            return line_clean
    
    return "Untitled Section"

def find_images_for_section(section_content: str, images_data: List[Dict]) -> List[Dict]:
    """Find images that belong to a specific section"""
    section_images = []
    
    for img in images_data:
        marker = img.get('position_marker', '')
        if marker and marker in section_content:
            section_images.append(img)
    
    return section_images

def smart_chunk_with_context(content: str, images_data: List[Dict], chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
    """Enhanced chunking that preserves image context and references"""
    
    chunks = []
    
    # Find all image marker positions in the content
    image_positions = {}
    for img in images_data:
        marker = img['position_marker']
        pos = content.find(marker)
        if pos != -1:
            image_positions[pos] = img
            logger.info(f"Found image marker '{marker}' at position {pos}")
        else:
            logger.warning(f"Image marker '{marker}' not found in content")
    
    logger.info(f"Found {len(image_positions)} image markers in content")
    
    # Split content into chunks
    start = 0
    chunk_index = 0
    
    while start < len(content):
        end = start + chunk_size
        chunk_text = content[start:end]
        
        # Adjust boundaries to preserve context (avoid breaking sentences/paragraphs)
        if end < len(content):
            # Try to break at sentence or paragraph boundaries
            last_period = chunk_text.rfind('.')
            last_newline = chunk_text.rfind('\n\n')
            last_single_newline = chunk_text.rfind('\n')
            
            # Choose the best break point
            break_point = max(last_period, last_newline, last_single_newline)
            
            if break_point > start + chunk_size // 2:  # Only use break point if it's not too early
                chunk_text = content[start:break_point + 1]
                end = break_point + 1
        
        # Find images that appear in this chunk
        chunk_images = []
        for pos, img_data in image_positions.items():
            if start <= pos < end:
                chunk_images.append(img_data)
                logger.info(f"Chunk {chunk_index}: Including image {img_data['filename']}")
        
        # Create chunk metadata
        chunk_data = {
            "content": chunk_text.strip(),
            "chunk_index": chunk_index,
            "start_position": start,
            "end_position": end,
            "images": chunk_images,
            "has_images": len(chunk_images) > 0
        }
        
        chunks.append(chunk_data)
        
        # Log chunk info
        logger.info(f"Chunk {chunk_index}: {len(chunk_text)} chars, {len(chunk_images)} images")
        
        chunk_index += 1
        start = end - overlap
        
        if start >= len(content):
            break
    
    logger.info(f"Created {len(chunks)} chunks total")
    return chunks

    
def create_combined_description(all_descriptions: dict, filename: str) -> str:
    """Create a comprehensive description combining all vision model outputs"""
    
    # Header
    combined = f"=== Multi-Model Vision Analysis for {filename} ===\n\n"
    
    # Priority order for display
    model_priority = ["OpenAI", "HuggingFace", "Enhanced Local", "Basic Fallback"]
    
    # Add each model's description
    for model in model_priority:
        if model in all_descriptions:
            description = all_descriptions[model]
            combined += f"**{model} Analysis:**\n{description}\n\n"
    
    # Add any models not in priority list
    for model, description in all_descriptions.items():
        if model not in model_priority:
            combined += f"**{model} Analysis:**\n{description}\n\n"
    
    # Summary section
    combined += "**Analysis Summary:**\n"
    combined += f"- Total models used: {len(all_descriptions)}\n"
    combined += f"- Models: {', '.join(all_descriptions.keys())}\n"
    
    # Extract key insights (basic analysis)
    insights = extract_key_insights(all_descriptions)
    if insights:
        combined += f"- Key insights: {insights}\n"
    
    combined += "\n" + "="*50 + "\n"
    
    return combined


def extract_key_insights(all_descriptions: dict) -> str:
    """Extract key insights from multiple descriptions"""
    insights = []
    
    # Combine all description text
    all_text = " ".join(all_descriptions.values()).lower()
    
    # Size indicators
    if "high-resolution" in all_text:
        insights.append("High quality image")
    elif "small" in all_text:
        insights.append("Small/low resolution")
    
    return ", ".join(insights[:3])  # Limit to top 3 insights


def process_document_with_context_multi_model(file_content: bytes, 
                                            filename: str, 
                                            temp_dir: str, 
                                            doc_id: str, 
                                            openai_api_key: str = None, 
                                            run_all_models: bool = True, 
                                            selected_models: set[str] = frozenset(),
                                            vision_flags: dict[str,bool] = {}) -> Dict:
    """Process document with multi-model vision option"""
    
    file_extension = Path(filename).suffix.lower()
    images_data = []

    # Extract images from file
    if file_extension == '.pdf':
        # 1) extract images synchronously
        pages_data = extract_and_store_images_from_file(file_content, filename, temp_dir, doc_id)

        # 2) run async describer on its own loop
        loop = asyncio.new_event_loop()
        try:
            pages_data = loop.run_until_complete(
                describe_images_for_pages(
                    pages_data,
                    api_key_override=openai_api_key,
                    run_all_models=run_all_models,
                    enabled_models=selected_models,
                    vision_flags=vision_flags
                )
            )
        finally:
            loop.close()

        # 3) Flatten all image data
        for page in pages_data:
            for img_path, desc in zip(page["images"], page.get("image_descriptions", [])):
                images_data.append({
                    "filename": Path(img_path).name,
                    "storage_path": img_path,
                    "description": desc,
                    "position_marker": f"[IMAGE:{Path(img_path).name}]",
                    "page": page["page"]
                })

    # Rest of processing remains the same as your existing function...
    temp_file_path = os.path.join(temp_dir, filename)
    with open(temp_file_path, 'wb') as f:
        f.write(file_content)

    try:
        md_instance = get_markitdown_instance(openai_api_key)
        result = md_instance.convert(temp_file_path)
        content = result.text_content if hasattr(result, 'text_content') else str(result)
        logger.info(f"MarkItDown extracted content length: {len(content)} characters")
    except Exception as e:
        logger.error(f"MarkItDown processing failed for {filename}: {e}")
        if file_extension == '.txt':
            content = file_content.decode('utf-8', errors='ignore')
        else:
            content = f"Document: {filename}\n\nContent could not be extracted via MarkItDown."

    # Enhanced image integration strategy (same as before)
    if images_data:
        logger.info(f"Integrating {len(images_data)} images into document content")
        
        if len(content.strip()) < 50:
            logger.info("Content is minimal, creating structured document with images")
            enhanced_content = [f"Document: {filename}\n"]
            
            pages_with_images = {}
            for img_data in images_data:
                page_num = img_data.get("page", 1)
                if page_num not in pages_with_images:
                    pages_with_images[page_num] = []
                pages_with_images[page_num].append(img_data)
            
            for page_num in sorted(pages_with_images.keys()):
                enhanced_content.append(f"\n--- Page {page_num} ---\n")
                for img_data in pages_with_images[page_num]:
                    enhanced_content.append(f"{img_data['position_marker']}")
                    enhanced_content.append(f"Image Description: {img_data['description']}\n")
            
            content = "\n".join(enhanced_content)
        
        else:
            logger.info("Inserting images into existing content")
            
            if '\n\n' in content:
                sections = content.split('\n\n')
                separator = '\n\n'
            else:
                sections = content.split('\n')
                separator = '\n'
            
            enhanced_sections = []
            images_inserted = 0
            
            for i, section in enumerate(sections):
                enhanced_sections.append(section)
                
                if (images_inserted < len(images_data) and 
                    i > 0 and 
                    (i % max(1, len(sections) // len(images_data)) == 0)):
                    
                    img_data = images_data[images_inserted]
                    image_section = f"\n{img_data['position_marker']}\nImage Description: {img_data['description']}\n"
                    enhanced_sections.append(image_section)
                    images_inserted += 1
                    logger.info(f"Inserted image {images_inserted}: {img_data['filename']}")
            
            while images_inserted < len(images_data):
                img_data = images_data[images_inserted]
                image_section = f"\n{img_data['position_marker']}\nImage Description: {img_data['description']}\n"
                enhanced_sections.append(image_section)
                images_inserted += 1
                logger.info(f"Added remaining image {images_inserted}: {img_data['filename']}")
            
            content = separator.join(enhanced_sections)
        
        logger.info(f"Final content length after image integration: {len(content)} characters")

    return {
        "content": content,
        "images_data": images_data,
        "file_type": file_extension
    }



def create_chunks_with_position_support(
    ext: str,
    pages_data: List[Dict],
    fname: str,
    content: bytes,
    tmp_dir: str,
    openai_api_key: Optional[str],
    vision_models: List[str],
    chunk_size: int,
    chunk_overlap: int,
    enable_ocr: bool,
    use_positions: bool = True
) -> List[Dict[str, Any]]:
    """
    Create chunks with optional position preservation.

    For PDFs with position-aware extraction enabled, uses position-aware chunking.
    Otherwise, falls back to legacy chunking logic.

    Args:
        ext: File extension (.pdf, .docx, etc.)
        pages_data: Page data from extraction (with or without positions)
        fname: Filename
        content: File content bytes
        tmp_dir: Temporary directory
        openai_api_key: OpenAI API key
        vision_models: List of vision models to use
        chunk_size: Chunk size for text splitting
        chunk_overlap: Chunk overlap for text splitting
        enable_ocr: Whether OCR is enabled
        use_positions: Whether to use position-aware chunking

    Returns:
        List of chunk dictionaries
    """
    # Check if we should use position-aware chunking
    if use_positions and USE_POSITION_AWARE and ext == ".pdf":
        logger.info(f"Using position-aware chunking for {fname}")
        try:
            # Use position-aware chunking from the new module
            chunks = page_based_chunking_with_positions(
                pages_data=pages_data,
                document_name=fname
            )
            logger.info(f"Position-aware chunking created {len(chunks)} chunks for {fname}")
            return chunks
        except Exception as e:
            logger.error(f"Position-aware chunking failed for {fname}, falling back to legacy: {e}")
            # Fall through to legacy chunking

    # Legacy chunking logic
    logger.info(f"Using legacy chunking for {fname}")

    use_page_chunking = True if ext == ".pdf" else False

    if use_page_chunking:
        # Extract page texts and correlate with images
        page_texts = extract_text_by_page(content, fname, tmp_dir)
        page_text_map = {p["page"]: (p.get("text") or "") for p in page_texts}

        chunks = []
        for page in pages_data:
            pg = page.get("page") or 0
            pg_text = page_text_map.get(pg, "")
            img_list = []
            for img_path, desc in zip(page.get("images", []), page.get("image_descriptions", [])):
                img_list.append({
                    "filename": Path(img_path).name,
                    "storage_path": img_path,
                    "description": desc,
                })
            page_ocr_used = False
            # OCR fallback if no text extracted
            if enable_ocr and not (pg_text or "").strip() and img_list:
                ocr_texts = []
                for img in img_list:
                    try:
                        with Image.open(img["storage_path"]) as im:
                            ocr_text = pytesseract.image_to_string(im)
                            if ocr_text and ocr_text.strip():
                                ocr_texts.append(ocr_text.strip())
                    except Exception as e:
                        logger.warning(f"OCR failed for image {img['filename']}: {e}")
                if ocr_texts:
                    pg_text = "\n".join(ocr_texts)
                    page_ocr_used = True
            # Ensure we have some minimal content to embed
            if not (pg_text or "").strip():
                pg_text = f"Page {pg}: [no extractable text]"
            chunks.append({
                "content": pg_text.strip(),
                "chunk_index": max(0, int(pg) - 1),
                "images": img_list,
                "page_number": pg,
                "section_type": "page",
                "section_title": "",
                "has_images": len(img_list) > 0,
                "ocr_used": page_ocr_used,
                "start_position": 0,
                "end_position": len(pg_text or ""),
            })
        logger.info(f"Legacy page-based chunking created {len(chunks)} chunks for {fname}")
    else:
        # full-document processing for non-PDF files
        doc_data = process_document_with_context_multi_model(
            file_content=content,
            filename=fname,
            temp_dir=tmp_dir,
            doc_id=fname,
            openai_api_key=openai_api_key,
            run_all_models=len(vision_models) > 1,
            selected_models=set(vision_models),
            vision_flags={m: (m in vision_models) for m in vision_models},
        )

        # Structure-preserving processing → embed → insert
        try:
            if use_structure_preserving_upload():
                logger.info(f"Using structure-preserving upload for {fname}")
                chunks = structure_preserving_process(doc_data["content"],
                                                    doc_data["images_data"],
                                                    fname)
                logger.info(f"Structure-preserving processing completed: {len(chunks)} chunks")
            else:
                # Fallback to original chunking
                logger.info(f"Using traditional chunking for {fname}")
                chunks = smart_chunk_with_context(doc_data["content"],
                                              doc_data["images_data"],
                                              chunk_size, chunk_overlap)
                logger.info(f"Traditional chunking completed: {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Structure-preserving processing failed for {fname}, falling back: {e}")
            chunks = smart_chunk_with_context(doc_data["content"],
                                          doc_data["images_data"],
                                          chunk_size, chunk_overlap)

    return chunks


def run_ingest_job(
    job_id: str,
    payloads: List[Dict[str, Any]],
    collection_name: str,
    chunk_size: int,
    chunk_overlap: int,
    store_images: bool,
    vision_models: List[str],
    openai_api_key: Optional[str],
    enable_ocr: bool,
):
    # initialize a hash: status + zeroed counters
    progress_key = f"job:{job_id}:progress"
    redis_client.set(job_id, "running")

    # initialize the hash strictly on the "progress" key
    redis_client.hset(progress_key, mapping={
        "total_chunks":     0,
        "processed_chunks": 0,
        "total_documents": len(payloads),
        "processed_documents": 0
    })

    # Initialize document status tracking
    for i, payload in enumerate(payloads):
        doc_status_key = f"job:{job_id}:doc:{i}"
        redis_client.hset(doc_status_key, mapping={
            "filename": payload["filename"],
            "status": "pending",  # pending, processing, completed, failed
            "chunks_total": 0,
            "chunks_processed": 0,
            "start_time": "",
            "end_time": "",
            "error_message": ""
        })

    # decide thread-pool size
    max_workers = min(4, os.cpu_count() or 1)

    def get_chromadb_collection():
        # Use the module-level chroma_client (HttpClient is thread-safe)
        return chroma_client.get_collection(name=collection_name)

    def process_one(item_with_index):
        item, doc_index = item_with_index
        fname = item["filename"]
        content = item["content"]
        document_id =  uuid.uuid4().hex 
        doc_status_key = f"job:{job_id}:doc:{doc_index}"

        # Update document status to processing
        redis_client.hset(doc_status_key, mapping={
            "status": "processing",
            "start_time": datetime.now().isoformat()
        })

        try:
            ext = Path(fname).suffix.lower()
            # 1) extract images and process document within same temp directory
            with tempfile.TemporaryDirectory() as tmp_dir:
                if ext == ".pdf":
                    # Use position-aware extraction wrapper (falls back to legacy if needed)
                    pages_data = extract_images_with_position_support(
                        file_content=content,
                        filename=fname,
                        temp_dir=tmp_dir,
                        doc_id=fname,
                        use_positions=True  # Can be controlled per-request if needed
                    )

                elif ext == ".docx":
                    pages_data = extract_images_from_docx(content, fname, tmp_dir, fname)

                elif ext == ".xlsx":
                    pages_data = extract_images_from_xlsx(content, fname, tmp_dir, fname)

                elif ext in (".html", ".htm"):
                    pages_data = extract_images_from_html(content, fname, tmp_dir, fname)

                else:
                    # txt, csv, pptx, etc → no images
                    pages_data = [{"page": 1, "images": [], "text": None}]

                # 2) describe images
                pages_data = asyncio.new_event_loop().run_until_complete(
                    describe_images_for_pages(
                        pages_data,
                        api_key_override=openai_api_key,
                        run_all_models=len(vision_models) > 1,
                        enabled_models=set(vision_models),
                        vision_flags={m: (m in vision_models) for m in vision_models},
                    )
                )

                # 2b) Merge descriptions back into image dicts for position-aware chunking
                for page in pages_data:
                    images = page.get("images", [])
                    descriptions = page.get("image_descriptions", [])

                    # Merge descriptions into image dictionaries
                    for i, img in enumerate(images):
                        if isinstance(img, dict) and i < len(descriptions):
                            img["description"] = descriptions[i]

                # 3) Build chunks using position-aware wrapper
                chunks = create_chunks_with_position_support(
                    ext=ext,
                    pages_data=pages_data,
                    fname=fname,
                    content=content,
                    tmp_dir=tmp_dir,
                    openai_api_key=openai_api_key,
                    vision_models=vision_models,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    enable_ocr=enable_ocr,
                    use_positions=True
                )

                # Validate chunks were created
                if not chunks:
                    msg = f"No chunks created for {fname}, skipping document"
                    logger.error(msg)
                    redis_client.hset(doc_status_key, mapping={
                        "status": "failed",
                        "end_time": datetime.now().isoformat(),
                        "error_message": msg
                    })
                    # Raise to abort processing this document (continue is invalid here)
                    raise RuntimeError(msg)

                # Update document chunk count
                redis_client.hset(doc_status_key, "chunks_total", len(chunks))

                # bump our total_chunks counter by however many we're about to insert
                redis_client.hincrby(progress_key, "total_chunks", len(chunks))
                coll = get_chromadb_collection()
                
                for c in chunks:
                    try:
                        text = c["content"]
                        # Debug: Log available fields in chunk
                        logger.debug(f"[{job_id}] Chunk {c.get('chunk_index', 'unknown')} fields: {list(c.keys())}")
                        # build metadata dict for this chunk - ChromaDB only accepts str, int, float, bool (NO None values)
                        meta = {
                            "document_id": document_id,
                            "document_name": fname,
                            "file_type": ext,
                            "chunk_index": c.get("chunk_index", 0),
                            "total_chunks": len(chunks),
                            # New structure-preserving metadata - ensuring no None values
                            "section_title": c.get("section_title", ""),
                            "section_type": c.get("section_type", "chunk"),
                            "page_number": c.get("page_number", -1),  # Use -1 instead of None
                            "section_number": c.get("section_number", -1),  # Use -1 instead of None
                            "has_images": c.get("has_images", False),
                            "image_count": len(c.get("images", [])),
                            "start_position": c.get("start_position", 0),
                            "end_position": c.get("end_position", len(text)),
                            "images_stored": store_images,
                            "timestamp": datetime.now().isoformat(),
                        }
                        
                        # Safe extraction of image metadata (handles both string paths and dict objects)
                        images_list = c.get("images", [])
                        filenames = []
                        paths = []
                        descs = []

                        for img in images_list:
                            if isinstance(img, dict):
                                filenames.append(img.get("filename", ""))
                                paths.append(img.get("storage_path", ""))
                                descs.append(img.get("description", ""))
                            elif isinstance(img, str):
                                # Legacy: img is a path string (Path is imported at top of file)
                                filenames.append(Path(img).name)
                                paths.append(img)
                                descs.append("")
                            else:
                                logger.warning(f"Unexpected image type: {type(img)}")
                                continue

                        meta["image_filenames"]     = json.dumps(filenames)
                        meta["image_storage_paths"] = json.dumps(paths)
                        meta["image_descriptions"]  = json.dumps(descs)

                        # Store image positions if available (from position-aware chunking)
                        if "image_positions" in c:
                            meta["image_positions"] = json.dumps(c["image_positions"])
                            logger.debug(f"[{job_id}] Stored {len(c['image_positions'])} image positions for chunk {c.get('chunk_index', 0)}")
                        else:
                            # Legacy chunks without position data
                            meta["image_positions"] = json.dumps([])

                        # Derive which vision models were used from description prefixes
                        models_used = set()
                        for d in descs:
                            if not d:
                                continue
                            ld = d.lower()
                            if ld.startswith("openai vision"):
                                models_used.add("openai")
                            elif ld.startswith("ollama vision"):
                                models_used.add("ollama")
                            elif ld.startswith("huggingface blip"):
                                models_used.add("huggingface")
                            elif ld.startswith("enhanced local"):
                                models_used.add("enhanced_local")
                            elif ld.startswith("basic fallback"):
                                models_used.add("basic")
                        meta["vision_models_used"] = json.dumps(sorted(models_used))
                        meta["openai_api_used"] = ("openai" in models_used)
                        meta["ocr_used"] = bool(c.get("ocr_used", False))
                        
                        # Validate metadata to ensure ChromaDB compatibility (no None values)
                        validated_meta = {}
                        for key, value in meta.items():
                            if value is None:
                                logger.warning(f"[{job_id}] Replacing None value for key '{key}' with empty string")
                                validated_meta[key] = ""
                            elif isinstance(value, (str, int, float, bool)):
                                validated_meta[key] = value
                            else:
                                logger.warning(f"[{job_id}] Converting non-standard type {type(value)} for key '{key}' to string")
                                validated_meta[key] = str(value)
                        meta = validated_meta
                        
                        # embed one chunk at a time
                        emb = embedding_model.encode([text], 
                                                    convert_to_numpy=True, 
                                                    batch_size=1).tolist()
                        chunk_id = f"{document_id}_chunk_{c.get('chunk_index', 0)}"
                        meta["chunk_id"] = chunk_id
                        coll.add(
                            documents=[text],
                            embeddings=emb,
                            metadatas=[meta],
                            ids=[chunk_id],
                        )
                        redis_client.hincrby(progress_key, "processed_chunks", 1)
                        redis_client.hincrby(doc_status_key, "chunks_processed", 1)
                        logger.info(f"[{job_id}] Ingested chunk {c['chunk_index']} for {fname} with {len(c.get('images', []))} images")
                    
                    except Exception as chunk_error:
                        logger.error(f"[{job_id}] Error processing chunk {c.get('chunk_index', 'unknown')} for {fname}: {chunk_error}")
                        # Mark this chunk as failed but continue with others
                        redis_client.hincrby(doc_status_key, "chunks_failed", 1)
                        continue

            # Document completed successfully
            redis_client.hset(doc_status_key, mapping={
                "status": "completed",
                "end_time": datetime.now().isoformat()
            })
            redis_client.hincrby(progress_key, "processed_documents", 1)
            return fname
            
        except Exception as e:
            # Document failed
            redis_client.hset(doc_status_key, mapping={
                "status": "failed",
                "end_time": datetime.now().isoformat(),
                "error_message": str(e)
            })
            logger.error(f"[{job_id}] Error processing document {fname}: {e}")
            raise

    # launch threads
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = { pool.submit(process_one, (p, i)): p["filename"] for i, p in enumerate(payloads) }
        for fut in as_completed(futures):
            fname = futures[fut]
            try:
                fut.result()
                logger.info(f"[{job_id}] Finished ingest of {fname}")
            except Exception as e:
                logger.error(f"[{job_id}] Error ingesting {fname}: {e!r}")

    # jobs[job_id] = "success"
    # redis_client.set(job_id, "success")
    redis_client.set(job_id, "success")

def extract_images_from_docx(file_content: bytes, filename: str, _temp_dir: str, doc_id: str):
    docx_path = os.path.join(_temp_dir, filename)
    with open(docx_path, "wb") as f:
        f.write(file_content)

    pages_data = [{"page": 1, "images": [], "text": None}]
    with ZipFile(docx_path) as z:
        for member in z.namelist():
            if member.startswith("word/media/"):
                data = z.read(member)
                name = f"{doc_id}_{Path(member).name}"
                out  = os.path.join(IMAGES_DIR, name)
                with open(out, "wb") as imgf:
                    imgf.write(data)
                pages_data[0]["images"].append(out)
    return pages_data

def extract_images_from_xlsx(file_content: bytes, filename: str, _temp_dir: str, doc_id: str):
    xlsx_path = os.path.join(_temp_dir, filename)
    with open(xlsx_path, "wb") as f:
        f.write(file_content)
    
    pages_data = [{"page": 1, "images": [], "text": None}] 
    
    with ZipFile(xlsx_path) as z:
        for m in z.namelist():
            if m.startswith("xl/media/"):
                data = z.read(m)
                name = f"{doc_id}_{Path(m).name}"
                out  = os.path.join(IMAGES_DIR, name)
                with open(out, "wb") as imgf:
                    imgf.write(data)
                pages_data[0]["images"].append(out)
    return pages_data

def extract_images_from_html(html_bytes, _filename, _temp_dir, doc_id):
    html = html_bytes.decode("utf8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    pages = [{"page":1, "images":[], "text": soup.get_text()}]
    for i, img in enumerate(soup.find_all("img"),1):
        src = img.get("src","")
        if src.startswith("data:image/"):
            header, b64 = src.split(",",1)
            ext = header.split(";")[0].split("/")[1]
            name = f"{doc_id}_{i}.{ext}"
            out  = os.path.join(IMAGES_DIR, name)
            with open(out,"wb") as f: f.write(base64.b64decode(b64))
        elif src.startswith("http"):
            resp = requests.get(src, timeout=10)
            ext  = Path(src).suffix or ".jpg"
            name = f"{doc_id}_{i}{ext}"
            out  = os.path.join(IMAGES_DIR, name)
            with open(out,"wb") as f: f.write(resp.content)
        else:
            continue
        pages[0]["images"].append(out)
    return pages
