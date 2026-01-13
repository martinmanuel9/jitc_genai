#!/usr/bin/env python3
"""
Verify heading-based chunking implementation.

This script:
1. Checks existing collections for old vs new chunking structure
2. Compares metadata fields
3. Shows statistics about chunks
"""

import requests
import json
from collections import defaultdict
from typing import Dict, List, Any

FASTAPI_URL = "http://localhost:9020"


def get_collections() -> List[str]:
    """Get all collections from ChromaDB"""
    resp = requests.get(f"{FASTAPI_URL}/api/vectordb/collections", timeout=10)
    resp.raise_for_status()
    return resp.json().get("collections", [])


def get_collection_metadata(collection_name: str) -> Dict[str, Any]:
    """Get metadata from all chunks in a collection"""
    resp = requests.get(
        f"{FASTAPI_URL}/api/vectordb/documents",
        params={"collection_name": collection_name},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def analyze_collection(collection_name: str):
    """Analyze a collection and show chunking type"""
    print(f"\n{'='*80}")
    print(f"Collection: {collection_name}")
    print(f"{'='*80}")

    try:
        data = get_collection_metadata(collection_name)

        ids = data.get("ids", [])
        metadatas = data.get("metadatas", [])

        if not ids:
            print("  ⚠️  Empty collection")
            return

        print(f"  Total chunks: {len(ids)}")

        # Analyze metadata structure
        first_meta = metadatas[0] if metadatas else {}

        # Check for new heading-based fields
        has_chunk_type = "chunk_type" in first_meta
        has_heading_text = "heading_text" in first_meta
        has_heading_level = "heading_level" in first_meta
        has_parent_heading = "parent_heading" in first_meta

        print(f"\n  Metadata Fields:")
        print(f"    chunk_type: {'✓' if has_chunk_type else '✗ (OLD CHUNKING)'}")
        print(f"    heading_text: {'✓' if has_heading_text else '✗ (OLD CHUNKING)'}")
        print(f"    heading_level: {'✓' if has_heading_level else '✗ (OLD CHUNKING)'}")
        print(f"    parent_heading: {'✓' if has_parent_heading else '✗ (OLD CHUNKING)'}")

        # Determine chunking type
        if has_chunk_type and has_heading_text:
            print(f"\n  ✅ Using NEW HEADING-BASED CHUNKING")

            # Count chunk types
            chunk_types = defaultdict(int)
            heading_levels = defaultdict(int)
            pages = set()
            documents = set()

            for meta in metadatas:
                chunk_type = meta.get("chunk_type", "unknown")
                chunk_types[chunk_type] += 1

                heading_level = meta.get("heading_level")
                if heading_level:
                    heading_levels[heading_level] += 1

                page = meta.get("page_number")
                if page is not None:
                    pages.add(page)

                doc_id = meta.get("document_id")
                if doc_id:
                    documents.add(doc_id)

            print(f"\n  Chunk Breakdown:")
            for chunk_type, count in sorted(chunk_types.items()):
                print(f"    {chunk_type}: {count}")

            print(f"\n  Heading Levels:")
            for level, count in sorted(heading_levels.items()):
                print(f"    H{level}: {count}")

            print(f"\n  Documents: {len(documents)}")
            for doc in sorted(documents):
                print(f"    - {doc}")

            print(f"\n  Pages: {len(pages)} (range: {min(pages) if pages else 0} - {max(pages) if pages else 0})")

            # Show sample heading
            heading_chunks = [m for m in metadatas if m.get("chunk_type") == "heading"]
            if heading_chunks:
                sample = heading_chunks[0]
                print(f"\n  Sample Heading Chunk:")
                print(f"    Text: {sample.get('heading_text')}")
                print(f"    Level: H{sample.get('heading_level')}")
                print(f"    Parent: {sample.get('parent_heading', 'None')}")
                print(f"    Page: {sample.get('page_number')}")
        else:
            print(f"\n  ⚠️  Using OLD PAGE-BASED CHUNKING")
            print(f"    This collection needs to be re-ingested with new chunking!")

            # Show old structure
            pages = set()
            documents = set()

            for meta in metadatas:
                page = meta.get("page_number")
                if page is not None:
                    pages.add(page)

                doc_id = meta.get("document_id")
                if doc_id:
                    documents.add(doc_id)

            print(f"\n  Documents: {len(documents)}")
            for doc in sorted(documents):
                print(f"    - {doc}")

            print(f"\n  Pages: {len(pages)} (roughly 1 chunk per page)")

            # Show what fields ARE present
            print(f"\n  Available Fields:")
            for key in sorted(first_meta.keys())[:10]:
                print(f"    - {key}")

    except Exception as e:
        print(f"  ❌ Error: {e}")


def main():
    print("=" * 80)
    print("HEADING-BASED CHUNKING VERIFICATION")
    print("=" * 80)

    try:
        collections = get_collections()

        # Filter out system/generated collections
        source_collections = [
            c for c in collections
            if not any(x in c for x in ["generated", "test_plan", "json_test"])
        ]

        if not source_collections:
            print("\n⚠️  No source document collections found!")
            print("Upload a PDF document to test the new chunking.")
            return

        print(f"\nFound {len(source_collections)} source collection(s)")

        for collection in source_collections:
            analyze_collection(collection)

        print(f"\n{'='*80}")
        print("RECOMMENDATIONS")
        print(f"{'='*80}")

        print("""
To test the new heading-based chunking:

1. Upload a new PDF document via Streamlit UI or API:

   curl -X POST http://localhost:9020/api/vectordb/upload \\
     -F "file=@your_document.pdf" \\
     -F "collection_name=test_new_chunking" \\
     -F "enable_vision=false"

2. Run this script again to verify new chunking structure

3. Generate a test plan from the new collection:
   - You should see sections based on actual headings (not just pages)
   - Metrics should show: X heading chunks, Y body chunks across Z pages

4. For old collections, re-ingest documents:
   - Delete old collection
   - Upload document again
   - Regenerate test plans
""")

    except Exception as e:
        print(f"\n❌ Error connecting to API: {e}")
        print(f"Make sure FastAPI is running at {FASTAPI_URL}")


if __name__ == "__main__":
    main()
