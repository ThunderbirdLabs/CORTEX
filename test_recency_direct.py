"""
Direct Recency Boost Test - Bypass SubQuestionQueryEngine

Tests recency boost directly on vector retrieval to see actual score changes.
"""

import sys
import os
import asyncio
from datetime import datetime
import logging

# Enable debug logging
logging.basicConfig(level=logging.INFO)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ingestion.llamaindex import HybridQueryEngine

async def test_direct_recency():
    """Test recency boost directly on vector engine."""

    print("="*80)
    print("DIRECT RECENCY BOOST TEST")
    print("="*80)

    # Initialize query engine
    print("\n1️⃣ Initializing HybridQueryEngine...")
    engine = HybridQueryEngine()
    print("✅ Engine initialized\n")

    # Test query
    query = "What materials do we use?"

    print(f"2️⃣ Testing direct vector query: '{query}'")
    print("   This bypasses SubQuestionQueryEngine to see raw recency boost\n")

    # Query vector engine directly
    result = engine.vector_query_engine.query(query)

    # Display results
    print("3️⃣ RESULTS:")
    print(f"   Answer: {result.response[:200]}...\n")

    print("4️⃣ SOURCE NODES WITH RECENCY BOOST:")
    source_nodes = result.source_nodes

    if source_nodes:
        for i, node in enumerate(source_nodes[:10], 1):
            metadata = node.node.metadata
            created_at_ts = metadata.get('created_at_timestamp')

            if created_at_ts:
                created_at = datetime.fromtimestamp(created_at_ts)
                age_days = (datetime.now() - created_at).days
                age_str = f"{age_days} days old"
            else:
                age_str = "No timestamp"

            score_str = f"{node.score:.4f}" if node.score is not None else "None"
            title = metadata.get('title', metadata.get('subject', 'Unknown'))

            print(f"\n   [{i}] Score: {score_str}")
            print(f"       Age: {age_str}")
            print(f"       Title: {title[:60]}...")
    else:
        print("   ⚠️ No source nodes returned")

    # Verification
    if source_nodes:
        print("\n" + "="*80)
        print("📊 VERIFICATION:")
        print("="*80)

        # Check score ordering
        scores = [node.score for node in source_nodes if node.score is not None]
        if len(scores) > 1:
            is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
            print(f"\n   Scores properly sorted: {'✅ YES' if is_sorted else '⚠️ NO'}")

        # Check age distribution
        timestamps = [
            node.node.metadata.get('created_at_timestamp')
            for node in source_nodes[:10]
        ]
        ages = [
            (datetime.now() - datetime.fromtimestamp(ts)).days
            for ts in timestamps if ts
        ]

        if ages:
            avg_age = sum(ages) / len(ages)
            print(f"   Average age of top 10 results: {avg_age:.1f} days")
            print(f"   Age range: {min(ages)} - {max(ages)} days")

            # Check if newer docs rank higher
            print("\n   📅 Age vs Position (should trend upward if recency boost working):")
            for i, age in enumerate(ages[:5], 1):
                print(f"      Position {i}: {age} days old")

    print("\n" + "="*80)
    print("✅ DIRECT RECENCY BOOST TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_direct_recency())
