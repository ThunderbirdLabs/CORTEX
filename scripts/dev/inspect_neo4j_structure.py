#!/usr/bin/env python3
"""
Inspect actual Neo4j structure to understand:
1. Where is text stored? (Chunk nodes only?)
2. What properties do entities have?
3. What properties do relationships have?
4. Do relationships have any link back to source text?
"""
import sys
sys.path.append('/Users/alexkashkarian/Desktop/cortex')

from app.services.ingestion.llamaindex.config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
)
from neo4j import GraphDatabase

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

with driver.session(database=NEO4J_DATABASE) as session:
    print("=" * 80)
    print("1. CHUNK NODE STRUCTURE")
    print("=" * 80)

    # Get a sample chunk node
    chunk_result = session.run("""
        MATCH (c:Chunk)
        RETURN c
        LIMIT 1
    """)

    for record in chunk_result:
        chunk = record["c"]
        print(f"\nChunk Node Properties:")
        for key, value in chunk.items():
            if key == "text":
                print(f"  - {key}: {value[:200]}..." if len(value) > 200 else f"  - {key}: {value}")
            else:
                print(f"  - {key}: {value}")

    print("\n" + "=" * 80)
    print("2. ENTITY NODE STRUCTURE (PERSON example)")
    print("=" * 80)

    # Get a sample person entity
    person_result = session.run("""
        MATCH (p:PERSON)
        RETURN p
        LIMIT 1
    """)

    for record in person_result:
        person = record["p"]
        print(f"\nPerson Node Properties:")
        for key, value in person.items():
            print(f"  - {key}: {value}")

    print("\n" + "=" * 80)
    print("3. RELATIONSHIP STRUCTURE")
    print("=" * 80)

    # Get sample relationships with their properties
    rel_result = session.run("""
        MATCH (a)-[r]->(b)
        WHERE type(r) IN ['WORKS_FOR', 'SUPPLIES_TO', 'CONTAINS', 'MENTIONS']
        RETURN type(r) as rel_type, properties(r) as props, labels(a) as source_labels, labels(b) as target_labels
        LIMIT 5
    """)

    print("\nRelationship Properties:")
    for record in rel_result:
        rel_type = record["rel_type"]
        props = record["props"]
        source_labels = record["source_labels"]
        target_labels = record["target_labels"]
        print(f"\n  {source_labels} -{rel_type}-> {target_labels}")
        if props:
            for key, value in props.items():
                print(f"    - {key}: {value}")
        else:
            print(f"    - (no properties)")

    print("\n" + "=" * 80)
    print("4. MENTIONS RELATIONSHIP (Chunk -> Entity)")
    print("=" * 80)

    # Check if MENTIONS relationships exist and what they link
    mentions_result = session.run("""
        MATCH (c:Chunk)-[r:MENTIONS]->(e)
        RETURN c.text as chunk_text, labels(e) as entity_labels, e.name as entity_name
        LIMIT 2
    """)

    print("\nMENTIONS Relationships:")
    for record in mentions_result:
        chunk_text = record["chunk_text"]
        entity_labels = record["entity_labels"]
        entity_name = record["entity_name"]
        chunk_preview = chunk_text[:150] + "..." if len(chunk_text) > 150 else chunk_text
        print(f"\n  Chunk: \"{chunk_preview}\"")
        print(f"  -> MENTIONS -> {entity_labels}: {entity_name}")

    print("\n" + "=" * 80)
    print("5. CAN WE TRACE RELATIONSHIP -> CHUNK -> TEXT?")
    print("=" * 80)

    # Try to find if we can trace a relationship back to its source text
    trace_result = session.run("""
        MATCH (p1:PERSON)-[r:WORKS_FOR]->(c:COMPANY)
        OPTIONAL MATCH (chunk:Chunk)-[:MENTIONS]->(p1)
        OPTIONAL MATCH (chunk)-[:MENTIONS]->(c)
        RETURN p1.name as person, c.name as company,
               collect(DISTINCT chunk.text)[0..2] as chunk_texts
        LIMIT 3
    """)

    print("\nTracing WORKS_FOR relationships to source text:")
    for record in trace_result:
        person = record["person"]
        company = record["company"]
        chunk_texts = record["chunk_texts"]

        print(f"\n  {person} WORKS_FOR {company}")
        if chunk_texts and chunk_texts[0]:
            for i, text in enumerate(chunk_texts):
                if text:
                    preview = text[:200] + "..." if len(text) > 200 else text
                    print(f"    Chunk {i+1}: \"{preview}\"")
        else:
            print(f"    (no chunk text found)")

driver.close()
