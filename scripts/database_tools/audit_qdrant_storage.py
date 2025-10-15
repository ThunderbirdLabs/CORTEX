"""
Deep Audit: Qdrant Storage Analysis

Retrieves ALL points from Qdrant and analyzes:
1. Text content formatting and quality
2. Metadata structure and completeness
3. Chunking strategy effectiveness
4. Search optimization opportunities
"""

import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import json

load_dotenv()

# Get config from environment
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "cortex_emails")

def audit_qdrant_storage():
    print("\n" + "="*80)
    print("QDRANT STORAGE DEEP AUDIT")
    print("="*80 + "\n")

    # Initialize Qdrant client
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY
    )

    # Get collection info
    collection_info = client.get_collection(QDRANT_COLLECTION_NAME)
    print(f"Collection: {QDRANT_COLLECTION_NAME}")
    print(f"Total Points: {collection_info.points_count}")
    print(f"Vector Size: {collection_info.config.params.vectors.size}")
    print(f"Distance Metric: {collection_info.config.params.vectors.distance}")
    print("\n" + "="*80 + "\n")

    # Scroll through ALL points
    points = []
    offset = None

    while True:
        result = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False  # Don't need the actual vectors for this audit
        )

        records, offset = result
        points.extend(records)

        if offset is None:
            break

    print(f"✅ Retrieved {len(points)} points for analysis\n")

    # Analyze each point
    metadata_keys = set()
    text_lengths = []
    chunk_samples = []
    metadata_samples = []

    for i, point in enumerate(points, 1):
        payload = point.payload

        # Collect metadata keys
        metadata_keys.update(payload.keys())

        # Analyze text content
        text = payload.get('text', '')
        text_lengths.append(len(text))

        # Store samples
        if i <= 3:  # Store first 3 for detailed inspection
            chunk_samples.append({
                'point_id': point.id,
                'text': text,
                'metadata': payload
            })

        # Collect unique metadata structures
        metadata_structure = {k: type(v).__name__ for k, v in payload.items()}
        if metadata_structure not in metadata_samples:
            metadata_samples.append(metadata_structure)

    # ========================================================================
    # ANALYSIS REPORT
    # ========================================================================

    print("="*80)
    print("📊 STORAGE ANALYSIS")
    print("="*80 + "\n")

    # 1. Metadata Keys
    print("1️⃣  METADATA KEYS PRESENT:")
    print("-" * 40)
    for key in sorted(metadata_keys):
        count = sum(1 for p in points if key in p.payload)
        percentage = (count / len(points)) * 100
        print(f"   • {key}: {count}/{len(points)} ({percentage:.1f}%)")

    # 2. Text Content Analysis
    print("\n2️⃣  TEXT CONTENT ANALYSIS:")
    print("-" * 40)
    avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
    min_length = min(text_lengths) if text_lengths else 0
    max_length = max(text_lengths) if text_lengths else 0

    print(f"   • Average Length: {avg_length:.0f} chars")
    print(f"   • Min Length: {min_length} chars")
    print(f"   • Max Length: {max_length} chars")
    print(f"   • Total Points: {len(points)}")

    # 3. Metadata Structure Variations
    print("\n3️⃣  METADATA STRUCTURE VARIATIONS:")
    print("-" * 40)
    for i, structure in enumerate(metadata_samples, 1):
        print(f"   Structure {i}:")
        for key, value_type in sorted(structure.items()):
            print(f"      • {key}: {value_type}")
        print()

    # 4. Detailed Chunk Samples
    print("="*80)
    print("📝 DETAILED CHUNK SAMPLES (First 3 Points)")
    print("="*80 + "\n")

    for i, sample in enumerate(chunk_samples, 1):
        print(f"\n{'='*80}")
        print(f"POINT {i}: ID = {sample['point_id']}")
        print(f"{'='*80}\n")

        # Metadata
        print("📋 METADATA:")
        print("-" * 40)
        for key, value in sample['metadata'].items():
            if key != 'text':  # We'll show text separately
                # Pretty print complex values
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, indent=2)
                else:
                    value_str = str(value)

                # Truncate long values
                if len(value_str) > 200:
                    value_str = value_str[:200] + "..."

                print(f"{key}:")
                print(f"  {value_str}\n")

        # Text content
        print("📄 TEXT CONTENT:")
        print("-" * 40)
        text = sample['text']
        print(f"Length: {len(text)} chars\n")

        # Show first 500 chars with formatting preserved
        preview = text[:500]
        print(preview)
        if len(text) > 500:
            print(f"\n... [{len(text) - 500} more characters]")
        print("\n")

    # ========================================================================
    # OPTIMIZATION RECOMMENDATIONS
    # ========================================================================

    print("="*80)
    print("💡 OPTIMIZATION RECOMMENDATIONS")
    print("="*80 + "\n")

    recommendations = []

    # Check for missing critical metadata
    critical_fields = ['document_name', 'source', 'document_type', 'reference_time']
    for field in critical_fields:
        missing_count = sum(1 for p in points if field not in p.payload or p.payload.get(field) is None)
        if missing_count > 0:
            recommendations.append(
                f"⚠️  {missing_count}/{len(points)} points missing '{field}' metadata"
            )

    # Check text length optimization
    if avg_length > 2000:
        recommendations.append(
            f"⚠️  Average chunk size ({avg_length:.0f} chars) may be too large. Consider smaller chunks (500-1000 chars) for better retrieval precision"
        )
    elif avg_length < 200:
        recommendations.append(
            f"⚠️  Average chunk size ({avg_length:.0f} chars) may be too small. Chunks might lack sufficient context"
        )

    # Check for text quality issues
    empty_text_count = sum(1 for p in points if not p.payload.get('text', '').strip())
    if empty_text_count > 0:
        recommendations.append(
            f"❌ {empty_text_count}/{len(points)} points have empty or whitespace-only text"
        )

    # Check metadata consistency
    if len(metadata_samples) > 2:
        recommendations.append(
            f"⚠️  Found {len(metadata_samples)} different metadata structures. Consider standardizing"
        )

    # Print recommendations
    if recommendations:
        for rec in recommendations:
            print(f"{rec}\n")
    else:
        print("✅ No critical issues found. Storage appears well-optimized.\n")

    # Final summary
    print("="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Total Points: {len(points)}")
    print(f"Unique Metadata Keys: {len(metadata_keys)}")
    print(f"Average Text Length: {avg_length:.0f} chars")
    print(f"Metadata Structures: {len(metadata_samples)}")
    print("="*80 + "\n")

if __name__ == "__main__":
    audit_qdrant_storage()
