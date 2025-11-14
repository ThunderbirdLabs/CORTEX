"""
Audit Qdrant for Email Thread Duplicates
Checks how many duplicate thread chunks exist in vector store
"""
import asyncio
from qdrant_client import QdrantClient
from collections import defaultdict

async def main():
    # Connect to Qdrant
    QDRANT_URL = "https://548c56e8-4540-4adc-9c27-311c37dfd84c.us-west-1-0.aws.cloud.qdrant.io"
    QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.9YR8jyKOwa7f3-xf61Yuv-iEiGT_K33sdMOvyRP7Z5Q"
    COLLECTION_NAME = "cortex_documents"

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    print("="*100)
    print("QDRANT DUPLICATE THREAD AUDIT")
    print("="*100)
    print()

    # Get collection info
    collection = client.get_collection(COLLECTION_NAME)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Total points: {collection.points_count:,}")
    print()

    # Scroll through all points and collect thread data
    print("Scrolling through all points...")
    offset = None
    batch_size = 100

    points_processed = 0
    thread_groups = defaultdict(list)  # thread_id -> list of points
    doc_types = defaultdict(int)
    no_thread_id = 0

    while True:
        results = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )

        points, next_offset = results

        if not points:
            break

        for point in points:
            points_processed += 1

            payload = point.payload or {}
            doc_type = payload.get('document_type', 'unknown')
            doc_types[doc_type] += 1

            # Check for thread_id in payload (from metadata)
            thread_id = payload.get('thread_id', '')

            if thread_id and doc_type == 'email':
                thread_groups[thread_id].append({
                    'point_id': point.id,
                    'document_id': payload.get('document_id'),
                    'title': payload.get('title', ''),
                    'created_at': payload.get('created_at', ''),
                    'text_preview': payload.get('text', '')[:100]
                })
            elif doc_type == 'email':
                no_thread_id += 1

        if points_processed % 1000 == 0:
            print(f"  Processed: {points_processed:,} points...")

        offset = next_offset
        if offset is None:
            break

    print(f"\n✅ Processed: {points_processed:,} points")
    print()

    print("="*100)
    print("DOCUMENT TYPE BREAKDOWN")
    print("="*100)
    for doc_type, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {doc_type:20s}: {count:,}")
    print()

    print("="*100)
    print("EMAIL THREAD ANALYSIS")
    print("="*100)
    print(f"Emails with thread_id: {sum(len(points) for points in thread_groups.values()):,}")
    print(f"Emails without thread_id: {no_thread_id:,}")
    print(f"Unique threads: {len(thread_groups):,}")
    print()

    # Find threads with multiple emails (duplicates)
    duplicate_threads = {tid: points for tid, points in thread_groups.items() if len(points) > 1}

    print(f"Threads with duplicates: {len(duplicate_threads):,}")
    print()

    if duplicate_threads:
        # Calculate waste
        total_points_in_dup_threads = sum(len(points) for points in duplicate_threads.values())
        unique_threads_count = len(duplicate_threads)
        wasted_points = total_points_in_dup_threads - unique_threads_count

        print(f"Points in duplicate threads: {total_points_in_dup_threads:,}")
        print(f"If deduplicated (keep 1 per thread): {unique_threads_count:,}")
        print(f"WASTED POINTS: {wasted_points:,} ({wasted_points/points_processed*100:.1f}% of total)")
        print()

        # Show top 10 worst offenders
        sorted_threads = sorted(duplicate_threads.items(), key=lambda x: len(x[1]), reverse=True)

        print("="*100)
        print("TOP 10 MOST DUPLICATED THREADS")
        print("="*100)

        for i, (thread_id, points) in enumerate(sorted_threads[:10], 1):
            print(f"\n{i}. Thread {thread_id[:40]}... ({len(points)} emails)")
            print("-"*100)

            # Show each email in thread
            for point in sorted(points, key=lambda x: x.get('created_at', ''), reverse=True)[:5]:
                print(f"  Doc {point['document_id']} | {point['created_at'][:10]} | {point['title'][:50]}")
                print(f"    Text: {point['text_preview']}...")

            if len(points) > 5:
                print(f"  ... and {len(points)-5} more emails in this thread")

    # Save full audit to file
    import json
    audit_data = {
        'total_points': points_processed,
        'document_types': dict(doc_types),
        'emails_with_thread_id': sum(len(points) for points in thread_groups.values()),
        'emails_without_thread_id': no_thread_id,
        'unique_threads': len(thread_groups),
        'duplicate_threads': len(duplicate_threads),
        'wasted_points': wasted_points if duplicate_threads else 0,
        'top_duplicate_threads': [
            {
                'thread_id': tid,
                'email_count': len(points),
                'emails': points
            }
            for tid, points in sorted_threads[:50]
        ]
    }

    with open('/tmp/qdrant_audit.json', 'w') as f:
        json.dump(audit_data, f, indent=2)

    print()
    print("="*100)
    print("AUDIT SAVED: /tmp/qdrant_audit.json")
    print("="*100)

if __name__ == "__main__":
    asyncio.run(main())
