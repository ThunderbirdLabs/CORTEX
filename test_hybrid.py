"""
Test Script: Hybrid Property Graph System
Tests the NEW recommended LlamaIndex architecture with true hybrid retrieval

Compares:
- OLD: Dual Pipeline (vector_pipeline + graph_pipeline + SubQuestionQueryEngine)
- NEW: Hybrid Property Graph (single unified index + multi-strategy retrieval)
"""

import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
import nest_asyncio

# Allow nested event loops
nest_asyncio.apply()

load_dotenv()

# Import NEW hybrid system
from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import (
    HybridPropertyGraphPipeline
)
from app.services.ingestion.llamaindex.hybrid_retriever import (
    create_hybrid_retriever
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_hybrid_system():
    """Test the NEW hybrid property graph system"""
    
    print("\n" + "="*80)
    print("TESTING NEW HYBRID PROPERTY GRAPH SYSTEM (LlamaIndex Recommended)")
    print("="*80 + "\n")
    
    # Sample test data (same as before for comparison)
    email_1 = """
    From: sarah.chen@techvision.io
    To: mike.johnson@techvision.io
    Date: October 10, 2025
    Subject: Q4 Planning Meeting

    Hi Mike,

    Let's schedule our Q4 planning meeting for next week. I'd like Jennifer Wong
    from Customer Success to join us, and we should loop in David Williams from
    MedTech Solutions since they're our biggest customer.

    Sarah works for TechVision as VP of Sales.
    Mike Johnson works for TechVision as Sales Director.
    Jennifer Wong is the Customer Success Manager at TechVision.

    Thanks,
    Sarah
    """

    email_2 = """
    From: mike.johnson@techvision.io
    To: sarah.chen@techvision.io
    Date: October 12, 2025
    Subject: Re: Q4 Planning Meeting

    Sarah,

    Sounds good! I'll set up the meeting with Jennifer Wong. She's been doing
    great work with our customers. Also, I talked to David Williams yesterday
    and he mentioned they want to expand their contract.

    Mike Johnson is the Sales Director at TechVision.
    David Williams is VP of Procurement at MedTech Solutions.

    Best,
    Mike
    """

    email_3 = """
    From: jennifer.wong@techvision.io
    To: sarah.chen@techvision.io, mike.johnson@techvision.io
    Date: October 14, 2025
    Subject: MedTech Expansion Opportunity

    Sarah and Mike,

    I just finished a call with David Williams from MedTech Solutions. They want
    to add 200 more user licenses. This is a huge opportunity!

    Jennifer Wong manages customer success at TechVision.
    Sarah Chen is the VP of Sales at TechVision.

    Let's discuss tomorrow!

    Jennifer
    """

    # Initialize hybrid pipeline
    logger.info("Initializing Hybrid Property Graph Pipeline...")
    pipeline = HybridPropertyGraphPipeline()

    try:
        print("\n🚀 Starting ingestion into HYBRID system...\n")

        results = []

        # Ingest email 1
        print("\n" + "="*80)
        print("📧 EPISODE 1: Q4 Planning Meeting")
        print("="*80 + "\n")

        result_1 = await pipeline.ingest_document(
            content=email_1,
            document_name="Q4 Planning Meeting",
            source="gmail",
            document_type="email",
            reference_time=datetime(2025, 10, 10, 9, 30),
            metadata={
                "from": "sarah.chen@techvision.io",
                "to": "mike.johnson@techvision.io",
                "subject": "Q4 Planning Meeting"
            }
        )
        results.append(result_1)

        # Ingest email 2
        print("\n" + "="*80)
        print("📧 EPISODE 2: Re: Q4 Planning Meeting")
        print("="*80 + "\n")

        result_2 = await pipeline.ingest_document(
            content=email_2,
            document_name="Re: Q4 Planning Meeting",
            source="gmail",
            document_type="email",
            reference_time=datetime(2025, 10, 12, 14, 15),
            metadata={
                "from": "mike.johnson@techvision.io",
                "to": "sarah.chen@techvision.io",
                "subject": "Re: Q4 Planning Meeting"
            }
        )
        results.append(result_2)

        # Ingest email 3
        print("\n" + "="*80)
        print("📧 EPISODE 3: MedTech Expansion Opportunity")
        print("="*80 + "\n")

        result_3 = await pipeline.ingest_document(
            content=email_3,
            document_name="MedTech Expansion Opportunity",
            source="gmail",
            document_type="email",
            reference_time=datetime(2025, 10, 14, 16, 45),
            metadata={
                "from": "jennifer.wong@techvision.io",
                "to": "sarah.chen@techvision.io, mike.johnson@techvision.io",
                "subject": "MedTech Expansion Opportunity"
            }
        )
        results.append(result_3)

        # Print ingestion summary
        print("\n" + "="*80)
        print("📊 INGESTION SUMMARY")
        print("="*80 + "\n")

        print(f"Episodes processed: {len(results)}")
        for i, result in enumerate(results, 1):
            status = "✅" if result['status'] == 'success' else "❌"
            print(f"\nEpisode {i}: {result['document_name']}")
            print(f"  Status: {status} {result['status']}")
            if result['status'] == 'error':
                print(f"  Error: {result.get('error')}")

        # Get statistics
        print("\n" + "="*80)
        print("📊 HYBRID SYSTEM STATISTICS")
        print("="*80 + "\n")

        stats = pipeline.get_stats()

        print("Unified Property Graph:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Now test HYBRID RETRIEVAL
        print("\n" + "="*80)
        print("🔍 TESTING HYBRID RETRIEVAL (Multi-Strategy)")
        print("="*80 + "\n")

        logger.info("Creating hybrid retriever...")
        retriever = create_hybrid_retriever(
            pipeline=pipeline,
            similarity_top_k=10,
            use_cypher=False  # Set to True to enable Cypher patterns
        )

        # Test queries
        test_queries = [
            "What is Sarah Chen working on?",
            "Who works at TechVision?",
            "What is Sarah Chen working on and who is she collaborating with?",
            "Tell me about the MedTech expansion opportunity"
        ]

        for i, question in enumerate(test_queries, 1):
            print(f"\n{'='*80}")
            print(f"Query {i}/{len(test_queries)}")
            print(f"{'='*80}")

            result = await retriever.query(question)

            print(f"\n❓ Question: {result['question']}")
            print(f"\n✅ Answer:\n{result['answer']}\n")
            print(f"📊 Retrieved {len(result['source_nodes'])} source nodes")

        # Verify data in Neo4j
        print("\n" + "="*80)
        print("🔍 VERIFYING NEO4J DATA")
        print("="*80 + "\n")

        await verify_neo4j_data(pipeline)

    finally:
        await pipeline.close()


async def verify_neo4j_data(pipeline):
    """Verify entities and relationships in Neo4j"""

    print("Checking entity types...\n")

    # Query for entity types
    result = pipeline.graph_store.structured_query("""
        MATCH (e:__Entity__)
        WITH labels(e) as all_labels
        UNWIND all_labels as label
        WITH label
        WHERE label <> '__Entity__'
        RETURN label as entity_type, count(*) as count
        ORDER BY count DESC
    """)

    if result:
        print("Entity Type Distribution:")
        for row in result:
            print(f"  {row['entity_type']:20} | {row['count']}")
    else:
        print("⚠️  No typed entities found")

    print("\n" + "="*80)
    print("Checking relationships...\n")

    # Query for relationships
    result = pipeline.graph_store.structured_query("""
        MATCH (e1:__Entity__)-[r]->(e2:__Entity__)
        RETURN
            [l IN labels(e1) WHERE l <> '__Entity__'][0] as from_type,
            e1.name as from_name,
            type(r) as rel_type,
            [l IN labels(e2) WHERE l <> '__Entity__'][0] as to_type,
            e2.name as to_name
        LIMIT 15
    """)

    if result:
        print("Sample Relationships:")
        for row in result:
            from_type = row['from_type'] or 'Entity'
            to_type = row['to_type'] or 'Entity'
            print(f"  [{from_type}] {row['from_name']} -[{row['rel_type']}]-> [{to_type}] {row['to_name']}")
    else:
        print("⚠️  No relationships found")

    print("\n" + "="*80)
    print("✅ VERIFICATION COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_hybrid_system())
