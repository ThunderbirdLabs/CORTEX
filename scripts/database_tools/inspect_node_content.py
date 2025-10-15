"""
Inspect the _node_content field to see where the text actually is
"""

import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import json

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "cortex_emails")

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Get first point
result = client.scroll(
    collection_name=QDRANT_COLLECTION_NAME,
    limit=1,
    with_payload=True,
    with_vectors=False
)

point = result[0][0]
print("\n" + "="*80)
print("INSPECTING FIRST POINT")
print("="*80 + "\n")

print("All payload keys:")
print(list(point.payload.keys()))
print()

# Parse the _node_content JSON
node_content_str = point.payload.get('_node_content', '')
if node_content_str:
    try:
        node_content = json.loads(node_content_str)
        print("\n_node_content parsed as JSON:")
        print(json.dumps(node_content, indent=2)[:2000])  # First 2000 chars

        # Check if there's a 'text' key in the parsed JSON
        if 'text' in node_content:
            print("\n\n✅ FOUND TEXT IN _node_content!")
            print("="*80)
            print(f"Text length: {len(node_content['text'])} chars")
            print("\nFirst 500 chars of text:")
            print(node_content['text'][:500])
        else:
            print("\n\n❌ NO 'text' field in _node_content")
            print("Available fields:", list(node_content.keys()))

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse _node_content as JSON: {e}")
else:
    print("❌ No _node_content field")

# Also check if there's a direct 'text' field
if 'text' in point.payload:
    print("\n\n✅ FOUND 'text' field directly in payload!")
    print(f"Text length: {len(point.payload['text'])} chars")
    print(point.payload['text'][:500])
else:
    print("\n\n❌ NO direct 'text' field in payload")
