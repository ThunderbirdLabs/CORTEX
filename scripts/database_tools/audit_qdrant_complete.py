"""
Complete Qdrant Storage Audit with Correct Text Extraction

LlamaIndex stores node data in '_node_content' as JSON.
This script properly extracts and analyzes the actual text content.
"""

import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import json

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "cortex_emails")

def audit_qdrant():
    print("\n" + "="*80)
    print("COMPLETE QDRANT STORAGE AUDIT")
    print("="*80 + "\n")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Get collection info
    collection_info = client.get_collection(QDRANT_COLLECTION_NAME)
    print(f"Collection: {QDRANT_COLLECTION_NAME}")
    print(f"Total Points: {collection_info.points_count}")
    print(f"Vector Size: {collection_info.config.params.vectors.size}")
    print(f"Distance: {collection_info.config.params.vectors.distance}")
    print("\n" + "="*80 + "\n")

    # Scroll all points
    points = []
    offset = None

    while True:
        result = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        records, offset = result
        points.extend(records)
        if offset is None:
            break

    print(f"✅ Retrieved {len(points)} points\n")

    # Parse and analyze
    analyzed_points = []
    text_lengths = []
    metadata_keys = set()

    for point in points:
        payload = point.payload

        # Extract text from _node_content
        node_content_str = payload.get('_node_content', '')
        text = ''
        parsed_metadata = {}

        if node_content_str:
            try:
                node_content = json.loads(node_content_str)
                text = node_content.get('text', '')
                parsed_metadata = node_content.get('metadata', {})
            except:
                pass

        text_lengths.append(len(text))

        # Collect all metadata keys
        metadata_keys.update(payload.keys())
        metadata_keys.update(parsed_metadata.keys())

        analyzed_points.append({
            'id': point.id,
            'text': text,
            'text_length': len(text),
            'payload_metadata': payload,
            'node_metadata': parsed_metadata
        })

    # ========================================================================
    # ANALYSIS
    # ========================================================================

    print("="*80)
    print("📊 STORAGE ANALYSIS")
    print("="*80 + "\n")

    # 1. Text Content Stats
    print("1️⃣  TEXT CONTENT STATISTICS:")
    print("-" * 40)
    avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
    min_length = min(text_lengths) if text_lengths else 0
    max_length = max(text_lengths) if text_lengths else 0

    print(f"   • Total Points: {len(points)}")
    print(f"   • Average Length: {avg_length:.0f} chars")
    print(f"   • Min Length: {min_length} chars")
    print(f"   • Max Length: {max_length} chars")

    # 2. Metadata Coverage
    print("\n2️⃣  METADATA COVERAGE:")
    print("-" * 40)

    critical_fields = {
        'document_name': 'Document title',
        'source': 'Source system (gmail, slack, etc)',
        'document_type': 'Document type (email, doc, etc)',
        'timestamp': 'Creation/reference time',
        'tenant_id': 'Multi-tenancy identifier',
        'user_id': 'User/owner identifier'
    }

    for field, description in critical_fields.items():
        count = sum(1 for p in analyzed_points
                   if field in p['payload_metadata'] or field in p['node_metadata'])
        percentage = (count / len(points)) * 100
        status = "✅" if percentage == 100 else "⚠️"
        print(f"   {status} {field}: {count}/{len(points)} ({percentage:.0f}%)")
        print(f"      └─ {description}")

    # 3. Sample Document Inspection
    print("\n" + "="*80)
    print("📝 DETAILED DOCUMENT SAMPLES (First 3)")
    print("="*80)

    for i, point_data in enumerate(analyzed_points[:3], 1):
        print(f"\n{'-'*80}")
        print(f"DOCUMENT {i}")
        print(f"{'-'*80}\n")

        # Key metadata
        doc_name = point_data['payload_metadata'].get('document_name', 'Unknown')
        doc_type = point_data['payload_metadata'].get('document_type', 'Unknown')
        source = point_data['payload_metadata'].get('source', 'Unknown')
        timestamp = point_data['payload_metadata'].get('timestamp', 'Unknown')

        print(f"📋 Metadata:")
        print(f"   • Title: {doc_name}")
        print(f"   • Type: {doc_type}")
        print(f"   • Source: {source}")
        print(f"   • Timestamp: {timestamp}")
        print(f"   • Text Length: {point_data['text_length']} chars")

        # Text sample
        print(f"\n📄 Text Content (first 400 chars):")
        print(f"{'-'*80}")
        text_preview = point_data['text'][:400]
        print(text_preview)
        if point_data['text_length'] > 400:
            print(f"\n... [{point_data['text_length'] - 400} more characters]")

    # ========================================================================
    # OPTIMIZATION ANALYSIS
    # ========================================================================

    print("\n\n" + "="*80)
    print("💡 OPTIMIZATION ANALYSIS")
    print("="*80 + "\n")

    issues = []
    recommendations = []

    # Check for empty text
    empty_count = sum(1 for p in analyzed_points if p['text_length'] == 0)
    if empty_count > 0:
        issues.append(f"❌ {empty_count}/{len(points)} points have no text content")

    # Check chunk size
    if avg_length > 2000:
        recommendations.append(
            f"⚠️  Average chunk size is {avg_length:.0f} chars. Consider smaller chunks (500-1000) for better precision."
        )
    elif avg_length > 0 and avg_length < 200:
        recommendations.append(
            f"⚠️  Average chunk size is {avg_length:.0f} chars. Chunks may lack context."
        )
    elif avg_length >= 500 and avg_length <= 1500:
        recommendations.append(
            f"✅ Chunk size ({avg_length:.0f} chars) is well-optimized for retrieval."
        )

    # Check metadata completeness
    for field in ['tenant_id', 'user_id', 'document_type', 'source']:
        missing = sum(1 for p in analyzed_points
                     if field not in p['payload_metadata'] and field not in p['node_metadata'])
        if missing > 0:
            issues.append(f"⚠️  {missing}/{len(points)} points missing '{field}' for filtering")

    # Check text field accessibility
    has_direct_text = any('text' in p['payload_metadata'] for p in analyzed_points)
    if not has_direct_text:
        recommendations.append(
            "📝 Text is stored in '_node_content' JSON field (LlamaIndex default). "
            "This is standard and works correctly with LlamaIndex retrievers."
        )

    # Print findings
    if issues:
        print("🔴 ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
        print()

    if recommendations:
        print("💡 RECOMMENDATIONS:")
        for rec in recommendations:
            print(f"   {rec}")
        print()

    if not issues:
        print("✅ No critical issues found!")
        print()

    # ========================================================================
    # SEARCH OPTIMIZATION CHECKLIST
    # ========================================================================

    print("="*80)
    print("🔍 SEARCH OPTIMIZATION CHECKLIST")
    print("="*80 + "\n")

    checklist = [
        ("Text content present", all(p['text_length'] > 0 for p in analyzed_points)),
        ("Chunk sizes reasonable (200-2000 chars)",
         all(200 <= p['text_length'] <= 2000 for p in analyzed_points if p['text_length'] > 0)),
        ("Document names present",
         all('document_name' in p['payload_metadata'] for p in analyzed_points)),
        ("Timestamps present",
         all('timestamp' in p['payload_metadata'] for p in analyzed_points)),
        ("Tenant IDs for multi-tenancy",
         all('tenant_id' in p['payload_metadata'] for p in analyzed_points)),
        ("Source tracking",
         all('source' in p['payload_metadata'] for p in analyzed_points)),
        ("Document type classification",
         all('document_type' in p['payload_metadata'] for p in analyzed_points)),
    ]

    for item, passed in checklist:
        status = "✅" if passed else "❌"
        print(f"   {status} {item}")

    # Final summary
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    print(f"Total Points: {len(points)}")
    print(f"Average Text Length: {avg_length:.0f} chars")
    print(f"Storage Format: LlamaIndex standard (_node_content)")
    print(f"Vector Size: {collection_info.config.params.vectors.size}D")
    print(f"Ready for Hybrid Retrieval: {'✅ Yes' if not issues else '⚠️  Issues found'}")
    print("="*80 + "\n")

if __name__ == "__main__":
    audit_qdrant()
