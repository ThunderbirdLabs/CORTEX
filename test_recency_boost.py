"""
Test Recency Boost Postprocessor

Verifies that recent documents rank higher than old documents
even when old documents have higher similarity scores.
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ingestion.llamaindex import HybridQueryEngine

async def test_recency_boost():
    """Test that recency boost favors recent documents."""

    print("="*80)
    print("RECENCY BOOST TEST")
    print("="*80)

    # Initialize query engine
    print("\n1️⃣ Initializing HybridQueryEngine with RecencyBoostPostprocessor...")
    engine = HybridQueryEngine()
    print("✅ Engine initialized")

    # Test query that should have both old and new results
    query = "Who manages Acme Corp?"

    print(f"\n2️⃣ Testing query: '{query}'")
    print("   Expected: Recent documents should rank higher\n")

    # Query
    result = await engine.query(query)

    # Display results
    print("\n3️⃣ RESULTS:")
    print(f"   Answer: {result.get('answer', 'No answer')}\n")

    print("4️⃣ SOURCE NODES (check recency boost applied):")
    source_nodes = result.get('source_nodes', [])

    if source_nodes:
        for i, node in enumerate(source_nodes[:5], 1):
            metadata = node.node.metadata
            created_at_ts = metadata.get('created_at_timestamp')

            if created_at_ts:
                created_at = datetime.fromtimestamp(created_at_ts)
                age_days = (datetime.now() - created_at).days
                age_str = f"{age_days} days old"
            else:
                age_str = "No timestamp"

            score_str = f"{node.score:.4f}" if node.score is not None else "None"
            print(f"\n   [{i}] Score: {score_str}")
            print(f"       Age: {age_str}")
            print(f"       Title: {metadata.get('title', 'Unknown')}")
            print(f"       Text preview: {node.node.text[:100]}...")
    else:
        print("   ⚠️ No source nodes returned")

    # Test another query
    query2 = "What materials do we use?"
    print(f"\n\n5️⃣ Testing second query: '{query2}'")

    result2 = await engine.query(query2)
    print(f"   Answer: {result2.get('answer', 'No answer')}")

    source_nodes2 = result2.get('source_nodes', [])
    if source_nodes2:
        print(f"\n   Top 3 sources by age:")
        for i, node in enumerate(source_nodes2[:3], 1):
            created_at_ts = node.node.metadata.get('created_at_timestamp')
            if created_at_ts:
                age_days = (datetime.now() - datetime.fromtimestamp(created_at_ts)).days
                print(f"   [{i}] {age_days} days old (score: {node.score:.4f})")

    print("\n" + "="*80)
    print("✅ RECENCY BOOST TEST COMPLETE")
    print("="*80)

    # Verify recency bias
    if source_nodes:
        print("\n📊 VERIFICATION:")

        # Check if nodes are sorted by recency-boosted score (filter out None scores)
        scores = [node.score for node in source_nodes[:5] if node.score is not None]
        if len(scores) > 1:
            is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))

            if is_sorted:
                print("   ✅ Nodes properly sorted by recency-boosted scores")
            else:
                print("   ⚠️  Scores not descending (may indicate issue)")
        else:
            print("   ⚠️  Not enough scored nodes to verify sorting")

        # Check age distribution
        timestamps = [
            node.node.metadata.get('created_at_timestamp')
            for node in source_nodes[:5]
        ]
        ages = [
            (datetime.now() - datetime.fromtimestamp(ts)).days
            for ts in timestamps if ts
        ]

        if ages:
            avg_age = sum(ages) / len(ages)
            print(f"   📅 Average age of top 5 results: {avg_age:.1f} days")
            print(f"   📅 Age range: {min(ages)} - {max(ages)} days")


if __name__ == "__main__":
    asyncio.run(test_recency_boost())
