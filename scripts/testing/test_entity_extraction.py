"""
Test Entity Extraction with SchemaLLMPathExtractor

Check what entities are being extracted from email bodies.
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from llama_index.core import Document
from llama_index.core.indices.property_graph import SimpleLLMPathExtractor
from llama_index.llms.openai import OpenAI
from app.services.ingestion.llamaindex.config import (
    OPENAI_API_KEY, EXTRACTION_MODEL, EXTRACTION_TEMPERATURE,
    ENTITIES, RELATIONS, VALIDATION_SCHEMA
)

async def test_extraction():
    """Test entity extraction on sample email."""

    # Sample email text
    email_text = """
Hi Emma,

I hope this message finds you well! I'm thrilled to welcome you and the Acme Corp team to Cortex.
We're excited to partner with you and help streamline your team's document search and email management.

As discussed in our kickoff call, Cortex integrates seamlessly with both Gmail and Outlook,
providing powerful search capabilities powered by our Qdrant vector database and Neo4j knowledge graph.

Our team at Thunderbird Labs has been working hard to ensure your onboarding goes smoothly.
Your account manager, Sarah Chen, will be reaching out to schedule your first training session.

Looking forward to working with you!

Best,
Alex Thompson
CEO, Cortex
"""

    print("="*80)
    print("ENTITY EXTRACTION TEST")
    print("="*80)
    print()

    print("Configuration:")
    print(f"  Model: {EXTRACTION_MODEL}")
    print(f"  Temperature: {EXTRACTION_TEMPERATURE}")
    print(f"  Extractor: SimpleLLMPathExtractor (more forgiving)")
    print()

    # Initialize extractor
    llm = OpenAI(
        model=EXTRACTION_MODEL,
        temperature=EXTRACTION_TEMPERATURE,
        api_key=OPENAI_API_KEY
    )

    extractor = SimpleLLMPathExtractor(
        llm=llm,
        max_paths_per_chunk=10,
        num_workers=4
    )

    # Create document
    doc = Document(text=email_text, metadata={"email_id": "test_123"})

    print("Extracting entities...")
    print()

    # Extract
    extracted = await extractor.acall([doc])

    print("="*80)
    print("EXTRACTION RESULTS")
    print("="*80)
    print()

    print(f"Total nodes returned: {len(extracted)}")
    print()

    for i, node in enumerate(extracted, 1):
        print(f"Node {i}:")
        print(f"  Type: {type(node)}")
        print(f"  Text preview: {node.text[:100]}...")
        print(f"  Metadata keys: {list(node.metadata.keys())}")
        print()

        # SimpleLLMPathExtractor uses 'nodes' and 'relations' keys
        entities = node.metadata.get("nodes", [])
        relations = node.metadata.get("relations", [])

        print(f"  Entities: {len(entities)}")
        print(f"  Relations: {len(relations)}")
        print()

        if entities:
            print("  Extracted Entities:")
            for entity in entities:
                print(f"    - {entity.label}: {entity.name}")
                if entity.properties:
                    for key, value in entity.properties.items():
                        print(f"      {key}: {value}")

        if relations:
            print("  Extracted Relations:")
            for rel in relations:
                print(f"    - {rel.label}: {rel.source_id} -> {rel.target_id}")
        print()

if __name__ == "__main__":
    asyncio.run(test_extraction())
