from fastapi import Query, BackgroundTasks, UploadFile, File, Request, Response
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from pathlib import Path
from services.document_ingestion_service import run_ingest_job
from integrations.chromadb_client import get_chroma_client

# Lazy initialization helper - returns client on first actual use
def chroma_client():
    """Wrapper to get ChromaDB client lazily."""
    return get_chroma_client()
# Position-aware reconstruction imports
from services.position_aware_reconstruction import (
    reconstruct_document_with_positions,
    insert_images_at_positions
)
import redis
import os
import uuid
import logging
import json

logger = logging.getLogger("VECTORDB_API")

vectordb_api_router = APIRouter(prefix="/vectordb", tags=["vectordb"])

openai_api_key = os.getenv("OPENAI_API_KEY", "")

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(redis_url, decode_responses=True)

# Image storage directory
IMAGES_DIR = os.path.join(os.getcwd(), "stored_images")
os.makedirs(IMAGES_DIR, exist_ok=True)

# Vision model configuration
VISION_CONFIG = {
    "openai_enabled": bool(openai_api_key),
    "ollama_enabled": True,
    "huggingface_enabled": True,
    "enhanced_local_enabled": True,
    "huggingface_model": os.getenv("HUGGINGFACE_VISION_MODEL", "Salesforce/blip-image-captioning-base"),
    # Ollama vision model mappings
    "ollama_models": {
        "llava_7b": "llava:7b",
        "llava_13b": "llava:13b",
        "granite_vision_2b": "granite3.2-vision:2b"
    }
}

# Position-aware reconstruction feature flag
USE_POSITION_AWARE_RECONSTRUCTION = os.getenv("USE_POSITION_AWARE_RECONSTRUCTION", "true").lower() == "true"
logger.info(f"Position-aware reconstruction: {'ENABLED' if USE_POSITION_AWARE_RECONSTRUCTION else 'DISABLED'}")

### ChromaDB Collection Endpoints ###
@vectordb_api_router.get("/collections")
def list_collections():
    try:
        collection_names = chroma_client().list_collections()  # Now returns just names
        return {"collections": collection_names}
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail="Failed to list collections")


@vectordb_api_router.post("/collection/create")
def create_collection(collection_name: str = Query(...)):
    """
    Create a ChromaDB collection with the given name.
    """
    try:
        # Get existing collection names safely
        existing_names = chroma_client().list_collections()
        
        if collection_name in existing_names:
            raise HTTPException(
                status_code=400,
                detail=f"Collection '{collection_name}' already exists."
            )
        
        chroma_client().create_collection(collection_name)
        logger.info(f"Created collection: {collection_name}")
        return {"created": collection_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating collection: {str(e)}")


@vectordb_api_router.get("/collection")
def get_collection_info(collection_name: str = Query(...)):
    """
    Get basic info about a single collection.
    """
    try:
        # Check if collection exists
        existing_names = chroma_client().list_collections()
                
        if collection_name not in existing_names:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name}' not found."
            )
        
        collection = chroma_client().get_collection(name=collection_name)
        return {"name": collection.name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting collection info: {str(e)}")


@vectordb_api_router.delete("/collection")
def delete_collection(collection_name: str = Query(...)):
    """
    Delete a ChromaDB collection by name.
    """
    try:
        # Get existing collection names safely
        existing_collections = chroma_client().list_collections()


        if collection_name not in existing_collections:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name}' not found."
            )

        chroma_client().delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")
        return {"deleted": collection_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting collection: {str(e)}")


@vectordb_api_router.put("/collection/edit")
def edit_collection_name(old_name: str = Query(...), new_name: str = Query(...)):
    """
    Rename a ChromaDB collection from 'old_name' to 'new_name'.
    """
    try:
        # Get existing collection names
        existing_names = chroma_client().list_collections()

        if old_name not in existing_names:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{old_name}' not found."
            )

        if new_name in existing_names:
            raise HTTPException(
                status_code=400,
                detail=f"Collection '{new_name}' already exists. Choose a different name."
            )

        # Retrieve the old collection
        collection = chroma_client().get_collection(name=old_name)

        # Create a new collection with the new name
        new_collection = chroma_client().create_collection(name=new_name)

        # Retrieve all documents from the old collection
        old_docs = collection.get()
        if old_docs and "ids" in old_docs and "documents" in old_docs:
            new_collection.add(ids=old_docs["ids"], documents=old_docs["documents"])

        # Delete the old collection
        chroma_client().delete_collection(old_name)

        return {"old_name": old_name, "new_name": new_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error editing collection: {str(e)}")


### Document Endpoints ###
class DocumentAddRequest(BaseModel):
    collection_name: str
    documents: list[str]
    ids: list[str]
    embeddings: list[list[float]] = None  
    metadatas: list[dict] = None           

@vectordb_api_router.post("/documents/add")
def add_documents(req: DocumentAddRequest):
    try:
        # Check if the collection exists
        existing_names = chroma_client().list_collections()
                
        if req.collection_name not in existing_names:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{req.collection_name}' not found."
            )
        
        # Retrieve the collection
        collection = chroma_client().get_collection(req.collection_name)
        
        # Add documents along with embeddings and metadatas
        collection.add(
            documents=req.documents,
            ids=req.ids,
            embeddings=req.embeddings,
            metadatas=req.metadatas
        )
        return {
            "collection": req.collection_name,
            "added_count": len(req.documents),
            "ids": req.ids
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding documents: {str(e)}")


class DocumentRemoveRequest(BaseModel):
    collection_name: str
    ids: list[str]

@vectordb_api_router.post("/documents/remove")
def remove_documents(req: DocumentRemoveRequest):
    """
    Remove documents by ID from a given collection.
    """
    try:
        # Check if the collection exists first
        existing_names = chroma_client().list_collections()
                
        if req.collection_name not in existing_names:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{req.collection_name}' not found."
            )

        # Now, safely retrieve the collection (since we verified it exists)
        collection = chroma_client().get_collection(req.collection_name)

        # Ensure at least one of the documents exists before attempting to delete
        existing_docs = collection.get()
        existing_ids = set(existing_docs.get("ids", []))

        if not any(doc_id in existing_ids for doc_id in req.ids):
            raise HTTPException(
                status_code=404,
                detail=f"None of the provided document IDs {req.ids} exist in collection '{req.collection_name}'."
            )

        # Delete the specified document(s)
        collection.delete(ids=req.ids)
        
        return {
            "collection": req.collection_name,
            "removed_ids": req.ids
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error removing documents: {str(e)}")


class DocumentEditRequest(BaseModel):
    collection_name: str
    doc_id: str
    new_document: str

@vectordb_api_router.post("/documents/edit")
def edit_document(req: DocumentEditRequest):
    """
    Replace the content of an existing document by ID.
    """
    try:
        # Check if the collection exists first
        existing_names = chroma_client().list_collections()
                
        if req.collection_name not in existing_names:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{req.collection_name}' not found."
            )

        # Now, safely retrieve the collection
        collection = chroma_client().get_collection(req.collection_name)

        # Ensure the document exists before attempting to update
        existing_docs = collection.get()
        if req.doc_id not in existing_docs.get("ids", []):
            raise HTTPException(
                status_code=404,
                detail=f"Document '{req.doc_id}' not found in collection '{req.collection_name}'."
            )

        # Delete the old document and re-add with new content
        collection.delete(ids=[req.doc_id])
        collection.add(documents=[req.new_document], ids=[req.doc_id])

        return {
            "collection": req.collection_name,
            "updated_id": req.doc_id,
            "new_document": req.new_document
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error editing document: {str(e)}")


@vectordb_api_router.get("/documents")
def list_documents(collection_name: str = Query(...)):
    """
    Get all documents (and their IDs) in a collection.
    """
    try:
        # Check if the collection exists first
        existing_names = chroma_client().list_collections()
                
        if collection_name not in existing_names:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found.")

        # Now, safely retrieve the collection
        collection = chroma_client().get_collection(name=collection_name)

        # Retrieve documents
        docs = collection.get()
        return docs
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


class DocumentQueryRequest(BaseModel):
    collection_name: str
    query_embeddings: list[list[float]]
    n_results: int = 5
    include: list[str] = ["documents", "metadatas", "distances"]

@vectordb_api_router.post("/documents/query")
def query_documents(req: DocumentQueryRequest):
    try:
        # Check if the collection exists first
        existing_names = chroma_client().list_collections()
                
        if req.collection_name not in existing_names:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{req.collection_name}' not found."
            )

        # Retrieve the collection
        collection = chroma_client().get_collection(req.collection_name)

        # Perform the query using the provided embeddings and parameters
        query_result = collection.query(
            query_embeddings=req.query_embeddings,
            n_results=req.n_results,
            include=req.include
        )
        return query_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying documents: {str(e)}")


@vectordb_api_router.post("/documents/upload-and-process-debug")
async def upload_debug(request: Request):
    """Debug endpoint to see raw request"""
    try:
        # Get raw body
        body = await request.body()
        logger.info(f"[DEBUG] Content-Type: {request.headers.get('content-type')}")
        logger.info(f"[DEBUG] Body length: {len(body)}")
        logger.info(f"[DEBUG] Body preview: {body[:500]}")

        # Try to parse form data
        form = await request.form()
        logger.info(f"[DEBUG] Form keys: {list(form.keys())}")
        for key in form.keys():
            value = form[key]
            logger.info(f"[DEBUG] Form[{key}]: type={type(value)}, value={value if not isinstance(value, bytes) else f'<bytes len={len(value)}>'}")

        return {"status": "ok", "form_keys": list(form.keys())}
    except Exception as e:
        logger.error(f"[DEBUG] Error: {e}")
        return {"error": str(e)}

@vectordb_api_router.post("/documents/upload-and-process")
async def upload_and_process_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),  # Changed from File(None) to File(...) to make it required
    collection_name: str = Query(...),
    chunk_size: int = Query(1000),
    chunk_overlap: int = Query(200),
    store_images: bool = Query(True),
    model_name: str = Query("none"),
    vision_models: str = Query(""),
    enable_ocr: bool = Query(False),
    request: Request = None,
):
    # Enhanced logging for debugging
    logger.info(f"Upload request received - Collection: {collection_name}")
    logger.info(f"Files parameter type: {type(files)}, Value: {files}")
    logger.info(f"Number of files: {len(files) if files else 0}")
    logger.info(f"Chunk settings: size={chunk_size}, overlap={chunk_overlap}")
    logger.info(f"Vision models: {vision_models}")

    if not files or len(files) == 0:
        logger.warning("Upload request received without files for collection '%s'", collection_name)
        logger.warning(f"Files value was: {files} (type: {type(files)})")
        raise HTTPException(status_code=400, detail="No files provided for upload")

    logger.info(f"Received {len(files)} file(s) for processing")
    for idx, f in enumerate(files):
        logger.info(f"  File {idx+1}: {f.filename} (content_type: {f.content_type})")

    # 1) Validate collection
    if collection_name not in chroma_client().list_collections():
        raise HTTPException(404, f"Collection '{collection_name}' not found")

    # 2) Generate a single job_id
    job_id = uuid.uuid4().hex
    # jobs[job_id] = "pending"
    redis_client.set(job_id, "pending")

    # 3) Slurp each UploadFile into memory so we can hand off raw bytes
    payloads: List[Dict[str,Any]] = []
    for f in files:
        content = await f.read()
        payloads.append({"filename": f.filename, "content": content})

    # 4) Kick off the background task
    selected_models = [m.strip() for m in vision_models.split(",") if m.strip()]
    background_tasks.add_task(
        run_ingest_job,
        job_id,
        payloads,
        collection_name,
        chunk_size,
        chunk_overlap,
        store_images,
        selected_models,
        request.headers.get("X-OpenAI-API-Key") or openai_api_key,
        enable_ocr,
    )

    # 5) Return immediately with the job ID
    return {"job_id": job_id}



def hybrid_reconstruct_document(chunks_data: List[Dict], base_image_url: str = "/api/vectordb/images") -> Dict[str, Any]:
    """
    Hybrid reconstruction function that supports both position-aware and legacy reconstruction.

    Checks if chunks have image_positions metadata. If so, uses position-aware reconstruction.
    Otherwise, falls back to legacy reconstruction method.

    Args:
        chunks_data: List of chunk dictionaries with content and metadata
        base_image_url: Base URL for image references

    Returns:
        Dictionary with reconstructed_content, images, metadata, and reconstruction_method
    """
    # Validate chunks_data is not empty
    if not chunks_data:
        logger.warning("No chunks provided for reconstruction")
        return {
            "reconstructed_content": "# No content available",
            "images": [],
            "metadata": {
                "file_type": "unknown",
                "total_images": 0,
                "processing_timestamp": "",
                "openai_api_used": False,
                "ocr_pages": 0,
                "vision_models_used": [],
                "reconstruction_method": "empty"
            }
        }

    # Check if any chunk has image_positions metadata (indicates position-aware chunking)
    has_position_data = False
    for chunk in chunks_data:
        md = chunk.get("metadata", {})
        img_pos = md.get("image_positions", "[]")
        try:
            positions = json.loads(img_pos) if isinstance(img_pos, str) else img_pos
            if positions and len(positions) > 0:
                has_position_data = True
                break
        except:
            pass

    # Use position-aware reconstruction if enabled and position data is available
    if USE_POSITION_AWARE_RECONSTRUCTION and has_position_data:
        logger.info(f"Using position-aware reconstruction (found position data in {len(chunks_data)} chunks)")
        try:
            reconstructed_content, images, metadata = reconstruct_document_with_positions(
                chunks_data=chunks_data,
                base_image_url=base_image_url
            )

            # Enrich metadata with fields from chunk metadata (for compatibility)
            first_chunk_meta = chunks_data[0].get("metadata", {}) if chunks_data else {}

            # Convert sets to lists for JSON serialization
            if "pages" in metadata and isinstance(metadata["pages"], set):
                metadata["pages"] = sorted(list(metadata["pages"]))
            if "vision_models_used" in metadata and isinstance(metadata["vision_models_used"], set):
                metadata["vision_models_used"] = sorted(list(metadata["vision_models_used"]))

            return {
                "reconstructed_content": reconstructed_content,
                "images": images,
                "metadata": {
                    **metadata,
                    "reconstruction_method": "position_aware",
                    "file_type": first_chunk_meta.get("file_type", "unknown"),
                    "processing_timestamp": first_chunk_meta.get("timestamp", ""),
                    "openai_api_used": first_chunk_meta.get("openai_api_used", False)
                }
            }
        except Exception as e:
            logger.error(f"Position-aware reconstruction failed, falling back to legacy: {e}")
            # Fall through to legacy reconstruction

    # Legacy reconstruction
    logger.info(f"Using legacy reconstruction for {len(chunks_data)} chunks")

    document_name = chunks_data[0].get("metadata", {}).get("document_name", "UNKNOWN")
    lines: list[str] = [f"# Document: {document_name}", ""]
    all_images = []
    ocr_pages = 0
    vision_union = set()
    image_counter = 1
    last_section_title = None

    for chunk in chunks_data:
        md = chunk["metadata"]
        content = chunk["content"] or ""

        # Heading decisions based on metadata
        section_title = md.get("section_title") or ""
        section_type = (md.get("section_type") or "").lower()

        if section_title and section_title != last_section_title:
            lines.append(f"## {section_title}")
            last_section_title = section_title
        elif not section_title and not section_type:
            # legacy: prepend page info if available
            legacy_page = md.get("page")
            if legacy_page:
                pass  # Do not add page headings per user preference

        # Aggregate per-chunk metadata for summary
        try:
            if md.get("ocr_used"):
                ocr_pages += 1
            vm_raw = md.get("vision_models_used")
            if vm_raw:
                vm_list = json.loads(vm_raw) if isinstance(vm_raw, str) else vm_raw
                if isinstance(vm_list, list):
                    for v in vm_list:
                        if isinstance(v, str):
                            vision_union.add(v)
        except Exception:
            pass

        # Replace image markers with markdown-style descriptions and collect image info
        if md.get("has_images"):
            try:
                image_filenames = json.loads(md.get("image_filenames", "[]"))
                image_paths = json.loads(md.get("image_storage_paths", "[]"))
                image_descriptions = json.loads(md.get("image_descriptions", "[]"))

                for filename, path, desc in zip(image_filenames, image_paths, image_descriptions):
                    markdown_img = (
                        f"\n\n[Image {image_counter}]:\n"
                        f"# Description:\n"
                        f"{(desc or '').strip()}\n"
                    )
                    marker = f"[IMAGE:{filename}]"
                    content = content.replace(marker, markdown_img)

                    all_images.append({
                        "filename": filename,
                        "storage_path": path,
                        "description": desc,
                        "exists": os.path.exists(path)
                    })
                    image_counter += 1
            except Exception as e:
                logger.error(f"Failed to insert images: {e}")

        lines.append(content)
        lines.append("")

    reconstructed_content = "\n".join(lines).strip()

    # Safely extract metadata from first chunk
    first_chunk_meta = chunks_data[0].get("metadata", {}) if chunks_data else {}

    return {
        "reconstructed_content": reconstructed_content,
        "images": all_images,
        "metadata": {
            "file_type": first_chunk_meta.get("file_type", "unknown"),
            "total_images": len(all_images),
            "processing_timestamp": first_chunk_meta.get("timestamp", ""),
            "openai_api_used": ("openai" in vision_union) or first_chunk_meta.get("openai_api_used", False),
            "ocr_pages": int(ocr_pages),
            "vision_models_used": sorted(list(vision_union)),
            "reconstruction_method": "legacy"
        }
    }


@vectordb_api_router.get("/documents/reconstruct/{document_id}")
def reconstruct_document(document_id: str, collection_name: str = Query(...), request: Request = None):
    """
    Reconstruct original document from stored chunks and images, using chunk metadata
    (section titles, section types, page numbers) to format headings and structure.

    Supports both position-aware reconstruction (images at correct positions) and
    legacy reconstruction (images appended to chunks).
    """
    try:
        collection = chroma_client().get_collection(name=collection_name)

        # Get all chunks for this document
        results = collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"]
        )

        if not results["ids"]:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

        # Sort chunks by chunk index
        chunks_data = []
        for i, chunk_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i] or {}  # Handle None metadata from ChromaDB
            chunks_data.append({
                "chunk_index": metadata.get("chunk_index", 0),
                "content": results["documents"][i] or "",
                "metadata": metadata
            })

        chunks_data.sort(key=lambda x: x["chunk_index"])

        # Build absolute image URL for browser rendering
        # IMPORTANT: Always use localhost for browser access, not Docker internal hostname
        # The request.url.netloc might be "fastapi:9020" (Docker internal) which browsers can't access
        base_url = "http://localhost:9020"
        base_image_url = f"{base_url}/api/vectordb/images"
        logger.info(f"Using base_image_url: {base_image_url}")

        # Use hybrid reconstruction (supports both position-aware and legacy)
        result = hybrid_reconstruct_document(
            chunks_data=chunks_data,
            base_image_url=base_image_url
        )

        # Safe access to document name
        doc_name = "Unknown"
        if chunks_data and chunks_data[0].get("metadata"):
            doc_name = chunks_data[0]["metadata"].get("document_name", "Unknown")

        return {
            "document_id": document_id,
            "document_name": doc_name,
            "total_chunks": len(chunks_data),
            "reconstructed_content": result["reconstructed_content"],
            "images": result["images"],
            "metadata": result["metadata"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reconstructing document: {str(e)}")


@vectordb_api_router.get("/images/{image_filename}")
def get_stored_image(image_filename: str):
    """
    Retrieve a stored image file.
    """
    image_path = os.path.join(IMAGES_DIR, image_filename)
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # Determine content type
        ext = Path(image_filename).suffix.lower()
        content_type = "image/jpeg" if ext == ".jpg" else "image/png"
        
        return Response(content=image_data, media_type=content_type)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading image: {str(e)}")
    
@vectordb_api_router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    # status = jobs.get(job_id)
    # if status is None:
    #     raise HTTPException(404, f"Job {job_id} not found")
    # return {"job_id": job_id, "status": status}
    
    status = redis_client.get(job_id)
    prog   = redis_client.hgetall(f"job:{job_id}:progress") or {}
    
    # Get document statuses
    documents = []
    total_docs = int(prog.get("total_documents", 0))
    
    for i in range(total_docs):
        doc_status_key = f"job:{job_id}:doc:{i}"
        doc_status = redis_client.hgetall(doc_status_key)
        if doc_status:
            documents.append({
                "index": i,
                "filename": doc_status.get("filename", ""),
                "status": doc_status.get("status", "pending"),
                "chunks_total": int(doc_status.get("chunks_total", 0)),
                "chunks_processed": int(doc_status.get("chunks_processed", 0)),
                "start_time": doc_status.get("start_time", ""),
                "end_time": doc_status.get("end_time", ""),
                "error_message": doc_status.get("error_message", "")
            })
    
    return {
        "job_id": job_id,
        "status": status,
        "total_chunks": int(prog.get("total_chunks", 0)),
        "processed_chunks": int(prog.get("processed_chunks", 0)),
        "total_documents": int(prog.get("total_documents", 0)),
        "processed_documents": int(prog.get("processed_documents", 0)),
        "documents": documents
    }
    
## html scraping 
class BaseScraper:
    def __init__(self, url: str):
        self.url = url
        self.soup = None

    def fetch(self):
        resp = requests.get(self.url, timeout=10)
        resp.raise_for_status()
        self.soup = BeautifulSoup(resp.text, "html.parser")

    def extract(self):
        # title
        title = (
            self.soup.find("meta", property="og:title") or
            self.soup.find("title")
        )
        title = title["content"] if title and title.get("content") else title.get_text(strip=True)

        # description (Readability could be swapped in here)
        desc_tag = self.soup.find("meta", property="og:description") or self.soup.find("meta", attrs={"name":"description"})
        description = desc_tag["content"].strip() if desc_tag else self.soup.get_text("\n", strip=True)

        # images: try og:image then all <img> in body
        images = []
        og = self.soup.find("meta", property="og:image")
        if og and og.get("content"):
            images.append(og["content"])
        else:
            for img in self.soup.select("img"):
                if src := img.get("src"):
                    images.append(requests.compat.urljoin(self.url, src))

        return {
            "title":       title,
            "description": description,
            "images":      list(dict.fromkeys(images)),
            "source_url":  self.url
        }

def download_images(urls: list[str], dest_folder: str = "downloaded_images") -> list[str]:
    os.makedirs(dest_folder, exist_ok=True)
    local_paths = []
    for u in urls:
        fn = os.path.basename(u.split("?",1)[0])
        out = os.path.join(dest_folder, fn)
        r = requests.get(u, stream=True); r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        local_paths.append(out)
    return local_paths


class URLIngestRequest(BaseModel):
    url: str
    collection_name: str

@vectordb_api_router.post("/ingest-url")
async def ingest_url(req: URLIngestRequest):
    # 1) Scrape the page HTML
    scraper = BaseScraper(req.url)
    scraper.fetch()
    html_content = scraper.soup.prettify().encode('utf-8')
    uid = uuid.uuid4().hex
    
    # 2) Prepare a temporary file payload
    filename = f"page_{uid}.html"
    payloads = [{"filename": filename, "content": html_content}]

    # 3) Ensure target collection exists
    if req.collection_name not in chroma_client().list_collections():
        chroma_client().create_collection(req.collection_name)

    # 4) Generate a job_id and synchronously run ingest job
    job_id = uuid.uuid4().hex
    # Using default chunk settings; adjust as needed or pull from config
    chunk_size = 1000
    chunk_overlap = 200
    store_images = True
    model_name = "html"
    selected_models = set([m for m in ['openai','ollama','huggingface','enhanced_local'] if VISION_CONFIG.get(f"{m}_enabled", False)])
    openai_api_key = os.getenv('OPENAI_API_KEY')

    try:
        # Direct call to your existing ingestion pipeline
        run_ingest_job(
            job_id=job_id,
            payloads=payloads,
            collection_name=req.collection_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            store_images=store_images,
            model_name=model_name,
            vision_models=list(selected_models),
            openai_api_key=openai_api_key,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest job failed: {e}")

    return {
        'status': 'ingested',
        'job_id': job_id,
        'collection': req.collection_name
    }
