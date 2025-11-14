"""
Audit Qdrant Payload Quality
Sample random points and analyze metadata bloat vs value
"""
import random
from qdrant_client import QdrantClient
import json

QDRANT_URL = "https://548c56e8-4540-4adc-9c27-311c37dfd84c.us-west-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.9YR8jyKOwa7f3-xf61Yuv-iEiGT_K33sdMOvyRP7Z5Q"
COLLECTION_NAME = "cortex_documents"

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

print("="*100)
print("QDRANT PAYLOAD QUALITY AUDIT")
print("="*100)
print()

# Get collection info
collection = client.get_collection(COLLECTION_NAME)
total_points = collection.points_count
print(f"Total points: {total_points:,}")
print()

# Scroll and collect random sample
print("Collecting sample of 100 random points...")
offset = None
all_point_ids = []

while True:
    results = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=100,
        offset=offset,
        with_payload=False,
        with_vectors=False
    )

    points, next_offset = results
    all_point_ids.extend([p.id for p in points])

    if len(all_point_ids) >= 1000 or next_offset is None:
        break

    offset = next_offset

# Random sample
sample_ids = random.sample(all_point_ids, min(100, len(all_point_ids)))

# Retrieve full payloads
sample_points = client.retrieve(
    collection_name=COLLECTION_NAME,
    ids=sample_ids,
    with_payload=True,
    with_vectors=False
)

print(f"Retrieved {len(sample_points)} sample points")
print()

# Analyze payload sizes and content
print("="*100)
print("PAYLOAD SIZE ANALYSIS")
print("="*100)
print()

payload_sizes = []
text_lengths = []
metadata_field_counts = []
duplicate_metadata = []  # Fields that exist in both payload and _node_content

for point in sample_points:
    payload = point.payload or {}

    # Calculate payload size
    payload_json = json.dumps(payload)
    payload_size = len(payload_json)
    payload_sizes.append(payload_size)

    # Text length
    text = payload.get('text', '')
    text_lengths.append(len(text))

    # Count metadata fields
    metadata_fields = [k for k in payload.keys() if k not in ['text', '_node_content', '_node_type', 'doc_id', 'ref_doc_id']]
    metadata_field_counts.append(len(metadata_fields))

    # Check for duplicate metadata in _node_content
    if '_node_content' in payload:
        try:
            node_content = json.loads(payload['_node_content']) if isinstance(payload['_node_content'], str) else payload['_node_content']
            node_metadata = node_content.get('metadata', {})

            # Find fields that exist in both payload and node_content.metadata
            duplicates = []
            for field in metadata_fields:
                if field in node_metadata and payload[field] == node_metadata[field]:
                    duplicates.append(field)

            if duplicates:
                duplicate_metadata.append({
                    'doc_id': payload.get('document_id'),
                    'duplicated_fields': duplicates
                })
        except:
            pass

# Statistics
print(f"Payload sizes:")
print(f"  Min:     {min(payload_sizes):,} bytes")
print(f"  Median:  {sorted(payload_sizes)[len(payload_sizes)//2]:,} bytes")
print(f"  Max:     {max(payload_sizes):,} bytes")
print(f"  Average: {sum(payload_sizes)//len(payload_sizes):,} bytes")
print()

print(f"Text lengths:")
print(f"  Min:     {min(text_lengths):,} chars")
print(f"  Median:  {sorted(text_lengths)[len(text_lengths)//2]:,} chars")
print(f"  Max:     {max(text_lengths):,} chars")
print(f"  Average: {sum(text_lengths)//len(text_lengths):,} chars")
print()

print(f"Metadata fields per point:")
print(f"  Min:     {min(metadata_field_counts)}")
print(f"  Median:  {sorted(metadata_field_counts)[len(metadata_field_counts)//2]}")
print(f"  Max:     {max(metadata_field_counts)}")
print(f"  Average: {sum(metadata_field_counts)/len(metadata_field_counts):.1f}")
print()

print(f"Duplicate metadata (in payload AND _node_content):")
print(f"  Points with duplicates: {len(duplicate_metadata)}/{len(sample_points)}")
if duplicate_metadata:
    all_dup_fields = set()
    for item in duplicate_metadata:
        all_dup_fields.update(item['duplicated_fields'])
    print(f"  Commonly duplicated fields: {', '.join(sorted(all_dup_fields))}")
print()

# Deep dive into worst offenders
print("="*100)
print("DETAILED ANALYSIS - 5 LARGEST PAYLOADS")
print("="*100)
print()

points_with_sizes = [(p, len(json.dumps(p.payload))) for p in sample_points]
largest = sorted(points_with_sizes, key=lambda x: x[1], reverse=True)[:5]

for i, (point, size) in enumerate(largest, 1):
    payload = point.payload

    print(f"\n{i}. POINT ID: {point.id}")
    print(f"   Payload size: {size:,} bytes")
    print("-"*100)

    # Show all fields
    print("   Fields:")
    for key, value in payload.items():
        if key == 'text':
            print(f"     {key}: {len(value):,} chars")
        elif key == '_node_content':
            print(f"     {key}: {len(str(value)):,} chars (serialized metadata)")
        elif isinstance(value, str):
            print(f"     {key}: '{value[:80]}{'...' if len(value) > 80 else ''}'")
        elif isinstance(value, (int, float)):
            print(f"     {key}: {value}")
        elif isinstance(value, list):
            print(f"     {key}: list with {len(value)} items")
        else:
            print(f"     {key}: {type(value).__name__}")

    # Check for bloat
    text_size = len(payload.get('text', ''))
    metadata_size = size - text_size

    print(f"\n   Analysis:")
    print(f"     Text: {text_size:,} bytes ({text_size/size*100:.1f}%)")
    print(f"     Metadata: {metadata_size:,} bytes ({metadata_size/size*100:.1f}%)")

    if metadata_size > text_size:
        print(f"     ⚠️  METADATA LARGER THAN TEXT (bloat!)")

# Check for pointless fields
print()
print("="*100)
print("FIELD USAGE ANALYSIS")
print("="*100)
print()

field_usage = {}
for point in sample_points:
    for key in point.payload.keys():
        if key not in field_usage:
            field_usage[key] = {'count': 0, 'empty': 0, 'sample_values': set()}

        field_usage[key]['count'] += 1
        value = point.payload[key]

        if not value or value == '' or value == [] or value == {}:
            field_usage[key]['empty'] += 1
        elif isinstance(value, str) and len(field_usage[key]['sample_values']) < 3:
            field_usage[key]['sample_values'].add(value[:50])

print("Fields by usage:")
for field, stats in sorted(field_usage.items(), key=lambda x: x[1]['count'], reverse=True):
    pct_used = (stats['count'] - stats['empty']) / stats['count'] * 100
    print(f"  {field:30s}: {stats['count']:3d} points, {pct_used:5.1f}% non-empty")
    if stats['empty'] > stats['count'] * 0.5:
        print(f"     ⚠️  MOSTLY EMPTY ({stats['empty']}/{stats['count']})")

print()
print("="*100)
print("RECOMMENDATIONS")
print("="*100)

# Save full audit
audit_data = {
    'total_points_sampled': len(sample_points),
    'payload_size_stats': {
        'min': min(payload_sizes),
        'median': sorted(payload_sizes)[len(payload_sizes)//2],
        'max': max(payload_sizes),
        'average': sum(payload_sizes)//len(payload_sizes)
    },
    'field_usage': {k: {'count': v['count'], 'empty': v['empty']} for k, v in field_usage.items()},
    'duplicate_metadata_count': len(duplicate_metadata)
}

with open('/tmp/qdrant_payload_audit.json', 'w') as f:
    json.dump(audit_data, f, indent=2)

print("\nFull audit saved: /tmp/qdrant_payload_audit.json")
