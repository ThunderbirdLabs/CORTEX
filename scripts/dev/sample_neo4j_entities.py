#!/usr/bin/env python3
"""
Sample actual entities from Neo4j to understand real-world patterns.
"""
import sys
sys.path.append('/Users/alexkashkarian/Desktop/cortex')

from app.services.ingestion.llamaindex.config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
)
from neo4j import GraphDatabase

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

with driver.session(database=NEO4J_DATABASE) as session:
    # Get sample of actual entities
    result = session.run("""
        MATCH (n)
        WHERE n:PERSON OR n:COMPANY OR n:MATERIAL OR n:PURCHASE_ORDER OR n:ROLE OR n:CERTIFICATION
        RETURN labels(n) as labels, n.name as name, n.email as email
        LIMIT 200
    """)

    entities_by_type = {}
    for record in result:
        label = record["labels"][0] if record["labels"] else "Unknown"
        name = record["name"]
        email = record.get("email")

        if label not in entities_by_type:
            entities_by_type[label] = []

        entity_info = {"name": name}
        if email:
            entity_info["email"] = email
        entities_by_type[label].append(entity_info)

    print("ACTUAL ENTITIES IN NEO4J:")
    print("=" * 80)
    for label, entities in sorted(entities_by_type.items()):
        print(f"\n{label} ({len(entities)} samples):")
        for entity in entities[:15]:  # Show first 15
            if "email" in entity:
                print(f"  - {entity['name']} ({entity['email']})")
            else:
                print(f"  - {entity['name']}")

    # Check for potential junk patterns
    print("\n\nPOTENTIAL JUNK ANALYSIS:")
    print("=" * 80)

    # Short names (possible junk)
    short_names = session.run("""
        MATCH (n:PERSON)
        WHERE size(n.name) < 5
        RETURN n.name as name
        LIMIT 20
    """)
    print("\nShort PERSON names (< 5 chars, possible junk):")
    for record in short_names:
        print(f"  - {record['name']}")

    # Generic terms
    generic_check = session.run("""
        MATCH (n)
        WHERE n.name IN ['meeting', 'call', 'email', 'document', 'project', 'order', 'material']
        RETURN labels(n) as labels, n.name as name
    """)
    print("\nGeneric terms found:")
    for record in generic_check:
        print(f"  - {record['name']} ({record['labels']})")

driver.close()
