from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session(database="neo4j") as session:
    # Check Chunk nodes with text
    print("="*80)
    print("CHUNK NODES (Document Text)")
    print("="*80 + "\n")
    
    result = session.run("""
        MATCH (c:Chunk)
        RETURN c.id as id, c.text as text, c.document_name as doc_name
        LIMIT 5
    """)
    
    for i, record in enumerate(result, 1):
        print(f"Chunk {i}:")
        print(f"  ID: {record['id']}")
        print(f"  Document: {record['doc_name']}")
        if record['text']:
            print(f"  Text ({len(record['text'])} chars): {record['text'][:200]}...")
        else:
            print(f"  Text: MISSING")
        print()

driver.close()
